"""Sync freshly scraped beef reports into the Demo global catalog.

After the scraper writes a report into its own tables (usda_reports /
usda_prices / usda_products), this pushes the same rows to Demo through
public.usda_boxed_beef_load(p jsonb) — deterministic (IMPS code → family,
report section → grade), idempotent per report (upsert on the observation's
unique key), so re-running is always safe.

Runs only when DEMO_SUPABASE_URL / DEMO_SUPABASE_KEY are set (Cloud Run job
usda-scraper-dev carries them as secrets; the GitHub Actions prod workflow does
not, so it is unaffected). Pork is not synced: Demo has no pork tree yet.

  python demo_sync.py                  # latest completed report per beef type
  python demo_sync.py --since 2026-09-01
  python demo_sync.py --all --dry-run  # full history, write nothing
"""
import argparse
import logging
import os

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

BEEF_REPORT_TYPES = ("daily_afternoon", "branded_beef", "ungraded_beef", "cow_beef")


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


def sync(report_types=BEEF_REPORT_TYPES, since=None, latest_only=True, dry_run=False) -> bool:
    """Push reports to Demo. Returns True when every report loaded (or dry run)."""
    types = [rt for rt in report_types if rt in BEEF_REPORT_TYPES]
    if not types:
        logger.info("demo sync: no beef report types requested, nothing to do")
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
        tag = f"{rep['report_type']} {rep['report_date']} ({len(payload['rows'])} rows)"
        if dry_run:
            logger.info(f"demo sync DRY {tag}")
            continue
        try:
            res = demo.rpc("usda_boxed_beef_load", {"p": payload}).execute().data or {}
        except Exception as e:  # network / PostgREST error
            logger.error(f"demo sync FAIL {tag}: {e}")
            ok = False
            continue
        if not res.get("ok"):
            logger.error(f"demo sync FAIL {tag}: {res.get('error')}")
            ok = False
            continue
        sk = res.get("skipped") or []
        totals["observations"] += res.get("observations", 0)
        totals["new_parts"] += res.get("new_parts", 0)
        totals["skipped"] += len(sk)
        logger.info(f"demo sync OK {tag}: {res.get('observations')} observations, "
                    f"{res.get('new_parts')} new products" + (f", {len(sk)} skipped" if sk else ""))
        for s in sk:
            logger.warning(f"demo sync skipped: {s.get('reason')} :: {s.get('line')}")
    if not dry_run:
        logger.info(f"demo sync done: {totals}")
    return ok


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="every completed report, oldest first")
    ap.add_argument("--since", help="reports on/after this date (YYYY-MM-DD)")
    ap.add_argument("--type", choices=BEEF_REPORT_TYPES, action="append", help="one report type (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="fetch and print, write nothing")
    args = ap.parse_args()
    if not args.dry_run and not demo_enabled():
        raise SystemExit("set DEMO_SUPABASE_URL and DEMO_SUPABASE_KEY")
    ok = sync(tuple(args.type) if args.type else BEEF_REPORT_TYPES,
              since=args.since, latest_only=not (args.all or args.since), dry_run=args.dry_run)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
