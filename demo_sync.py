"""Sync freshly scraped beef and poultry reports into the Demo global catalog.

After the scraper writes a report into its own tables (usda_reports /
usda_prices / usda_products), this pushes the same rows to Demo through a
door: public.usda_boxed_beef_load(p jsonb) for beef (IMPS code → family,
report section → grade) and public.usda_poultry_load(p jsonb) for the weekly
chicken and turkey reports (USDA item name → family, section → fresh/frozen
and basis). Both are deterministic and idempotent per report (upsert on the
observation's unique key), so re-running is always safe.

Runs only when DEMO_SUPABASE_URL / DEMO_SUPABASE_KEY are set (Cloud Run job
usda-scraper-dev carries them as secrets; the GitHub Actions prod workflow does
not, so it is unaffected). Pork is not synced: Demo has no pork tree yet.
Prime (prime_beef) never passes through the scraper's database: prime_report.py
fetches it from USDA and sends it here through send_to_demo().

  python demo_sync.py                  # latest completed report per beef and poultry type
  python demo_sync.py --since 2026-09-01
  python demo_sync.py --all --dry-run  # full history, write nothing
  python demo_sync.py --type weekly_chicken --type weekly_turkey --all
"""
import argparse
import logging
import os

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

BEEF_REPORT_TYPES = ("daily_afternoon", "branded_beef", "ungraded_beef", "cow_beef")
POULTRY_REPORT_TYPES = ("weekly_chicken", "weekly_turkey")
SYNCED_TYPES = BEEF_REPORT_TYPES + POULTRY_REPORT_TYPES
# Which Demo door takes a report type's rows.
DOORS = {**{t: "usda_boxed_beef_load" for t in BEEF_REPORT_TYPES},
         **{t: "usda_poultry_load" for t in POULTRY_REPORT_TYPES}}
# Reports that go to Demo only: fetched from USDA by their own module, never
# written to the scraper's database first (prime_report.py).
DEMO_ONLY_TYPES = ("prime_beef",)


def demo_enabled() -> bool:
    return bool(os.getenv("DEMO_SUPABASE_URL") and os.getenv("DEMO_SUPABASE_KEY"))


def _list_reports(src, report_types, since, latest_only):
    out = []
    for rt in report_types:
        q = (src.table("usda_reports")
                .select("id, report_type, report_date, pdf_url, status")
                .eq("report_type", rt).eq("status", "completed")
                .order("report_date", desc=True))
        if since:
            q = q.gte("report_date", since)
        q = q.limit(1) if latest_only else q.limit(2000)
        out.extend(q.execute().data or [])
    out.sort(key=lambda r: (r["report_date"], r["report_type"]))  # oldest first
    return out


def _load_products(src):
    """usda_prices has no FK to usda_products, so PostgREST cannot join; read once."""
    out, start, page = {}, 0, 1000
    while True:
        r = (src.table("usda_products").select("id, product_code, product_name")
                .range(start, start + page - 1).execute())
        for x in r.data or []:
            out[x["id"]] = x
        if len(r.data or []) < page:
            return out
        start += page


def _report_rows(src, report, products):
    r = (src.table("usda_prices")
            .select("product_id, category, price, low_price, high_price, volume")
            .eq("report_id", report["id"]).limit(5000).execute())
    rows = []
    for x in r.data or []:
        prod = products.get(x["product_id"]) or {}
        rows.append({
            "category": x["category"],
            "product_code": prod.get("product_code"),
            "product_name": prod.get("product_name"),
            "price": x["price"], "low_price": x["low_price"],
            "high_price": x["high_price"], "volume": x["volume"],
        })
    return rows


def _tag(payload) -> str:
    return f"{payload['report_type']} {payload['report_date']} ({len(payload['rows'])} rows)"


def send_to_demo(demo, payload):
    """One report -> its Demo door (DOORS; beef by default). Returns the door's result, or None on failure."""
    tag = _tag(payload)
    door = DOORS.get(payload.get("report_type"), "usda_boxed_beef_load")
    try:
        res = demo.rpc(door, {"p": payload}).execute().data or {}
    except Exception as e:  # network / PostgREST error
        logger.error(f"demo sync FAIL {tag}: {e}")
        return None
    if not res.get("ok"):
        logger.error(f"demo sync FAIL {tag}: {res.get('error')}")
        return None
    sk = res.get("skipped") or []
    logger.info(f"demo sync OK {tag}: {res.get('observations')} observations, "
                f"{res.get('new_parts')} new products" + (f", {len(sk)} skipped" if sk else ""))
    for x in sk:
        logger.warning(f"demo sync skipped: {x.get('reason')} :: {x.get('line')}")
    return res


def sync(report_types=SYNCED_TYPES, since=None, latest_only=True, dry_run=False) -> bool:
    """Push reports to Demo. Returns True when every report loaded (or dry run)."""
    types = [rt for rt in report_types if rt in SYNCED_TYPES]
    if not types:
        logger.info("demo sync: no beef or poultry report types requested, nothing to do")
        return True
    src = create_client(SUPABASE_URL, SUPABASE_KEY)
    reports = _list_reports(src, types, since, latest_only)
    logger.info(f"demo sync: {len(reports)} report(s) to load "
                f"({'latest per type' if latest_only else 'history'})")
    products = _load_products(src)
    demo = None if dry_run else create_client(os.environ["DEMO_SUPABASE_URL"], os.environ["DEMO_SUPABASE_KEY"])

    ok = True
    totals = {"observations": 0, "new_parts": 0, "skipped": 0}
    for rep in reports:
        payload = {"report_type": rep["report_type"], "report_date": rep["report_date"],
                   "pdf_url": rep.get("pdf_url"), "rows": _report_rows(src, rep, products)}
        if dry_run:
            logger.info(f"demo sync DRY {_tag(payload)}")
            continue
        res = send_to_demo(demo, payload)
        if res is None:
            ok = False
            continue
        totals["observations"] += res.get("observations", 0)
        totals["new_parts"] += res.get("new_parts", 0)
        totals["skipped"] += len(res.get("skipped") or [])
    if not dry_run:
        logger.info(f"demo sync done: {totals}")
    return ok


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="every completed report, oldest first")
    ap.add_argument("--since", help="reports on/after this date (YYYY-MM-DD)")
    ap.add_argument("--type", choices=SYNCED_TYPES + DEMO_ONLY_TYPES, action="append",
                    help="one report type (repeatable); prime_beef is fetched from USDA, not the scraper DB")
    ap.add_argument("--dry-run", action="store_true", help="fetch and print, write nothing")
    args = ap.parse_args()
    if not args.dry_run and not demo_enabled():
        raise SystemExit("set DEMO_SUPABASE_URL and DEMO_SUPABASE_KEY")
    types = tuple(args.type) if args.type else SYNCED_TYPES
    ok = True
    if set(types) & set(SYNCED_TYPES):
        ok = sync(types, since=args.since, latest_only=not (args.all or args.since), dry_run=args.dry_run)
    if "prime_beef" in types:
        import prime_report
        from datetime import date
        since = date.fromisoformat(args.since) if args.since else (date(2000, 1, 1) if args.all else None)
        ok = prime_report.sync(since=since, dry_run=args.dry_run) and ok
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
