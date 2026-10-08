"""USDA weekly Prime boxed beef cuts (LM_XB456 / AMS 2460) -> Demo only.

This report never touches the scraper's own database (usda_reports /
usda_prices): it is fetched from USDA's public LMR datamart API, parsed here,
and sent straight to Demo's door public.usda_boxed_beef_load as report_type
'prime_beef' (Demo stamps source = usda_prime_beef). It is a market feed, not a
client's data: any tenant whose products are USDA Prime picks it up.

Why the datamart and not the PDF: the PDF at /mnreports/ams_2460.pdf holds only
the latest week; the datamart serves every published week (keyless, JSON),
which also gives the backfill. The PDF footer points at the same API.

  python prime_report.py --dry-run                 # latest week, print the door payload
  python prime_report.py --since 2026-01-01        # every week since, send to Demo
  python prime_report.py --since 2025-01-01 --dry-run
"""
import argparse
import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

REPORT_TYPE = "prime_beef"
SLUG_ID = "2460"            # AMS 2460 = LM_XB456, National Weekly Boxed Beef Cuts for Prime Product
SECTION = "Prime Cuts"      # the datamart section name, also the row category the door reads as grade prime
DATAMART = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports"
PDF_URL = "https://www.ams.usda.gov/mnreports/ams_2460.pdf"

# "Rib, ribeye, lip-on, bn-in (109E  1)" -> description, IMPS, fat limitation.
# A codeless line prints "(  1)".
_ITEM = re.compile(r"^(?P<desc>.*?)\s*\((?P<imps>[0-9]{3}[A-Z]?)?\s+(?P<fl>\d+)\)\s*$")


def _num(v) -> Optional[float]:
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _iso(mdy: str) -> str:
    return datetime.strptime(mdy, "%m/%d/%Y").date().isoformat()


def _mdy(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def parse_rows(results: List[Dict]) -> List[Dict]:
    """Datamart 'Prime Cuts' results for ONE report date -> door rows.

    Row shape is the one demo_sync sends for the other beef reports:
    category, product_code, product_name ("IMPS - description"), price,
    low_price, high_price, volume. Lines with no trades (blank brackets such as
    "Loin, strip bnls, heavy (180  1)") and codeless lines are dropped here;
    the door would skip codeless lines anyway.
    """
    rows = []
    for r in results:
        m = _ITEM.match(r.get("item_description") or "")
        if not m or not m.group("imps"):
            continue
        trades = _num(r.get("number_trades"))
        price = _num(r.get("weighted_average"))
        if not trades or not price or price <= 0:
            continue
        code, desc = m.group("imps"), m.group("desc").strip()
        rows.append({
            "category": SECTION,
            "product_code": code,
            "product_name": f"{code} - {desc}",
            "price": price,
            "low_price": _num(r.get("price_range_low")),
            "high_price": _num(r.get("price_range_high")),
            "volume": _num(r.get("total_pounds")),
            "fat_limitation": int(m.group("fl")),
            "trades": int(trades),
        })
    return rows


def fetch(since: Optional[date] = None, until: Optional[date] = None, timeout: int = 60) -> Dict[str, List[Dict]]:
    """Datamart rows grouped by ISO report date. No dates = the latest week only."""
    url = f"{DATAMART}/{SLUG_ID}/{requests.utils.quote(SECTION)}"
    if since:
        until = until or date.today()
        url += f"?q=report_date={_mdy(since)}:{_mdy(until)}"
    else:  # latest: ask for the last 14 days, keep the newest date
        url += f"?q=report_date={_mdy(date.today() - timedelta(days=14))}:{_mdy(date.today())}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    by_date: Dict[str, List[Dict]] = {}
    for r in resp.json().get("results") or []:
        by_date.setdefault(_iso(r["report_date"]), []).append(r)
    if not since and by_date:
        newest = max(by_date)
        by_date = {newest: by_date[newest]}
    return dict(sorted(by_date.items()))


def payloads(since: Optional[date] = None, until: Optional[date] = None) -> List[Dict]:
    """One door payload per published week, oldest first."""
    out = []
    for d, results in fetch(since, until).items():
        out.append({"report_type": REPORT_TYPE, "report_date": d, "pdf_url": PDF_URL,
                    "rows": parse_rows(results)})
    return out


def sync(since: Optional[date] = None, until: Optional[date] = None, dry_run: bool = False) -> bool:
    """Fetch Prime from USDA and load it into Demo. Writes nowhere else."""
    from demo_sync import send_to_demo  # the door call shared with the other beef reports
    pls = payloads(since, until)
    logger.info(f"prime: {len(pls)} week(s) from the USDA datamart")
    if dry_run:
        for p in pls:
            logger.info(f"prime DRY {p['report_date']} ({len(p['rows'])} rows)")
        return True
    from supabase import create_client
    demo = create_client(os.environ["DEMO_SUPABASE_URL"], os.environ["DEMO_SUPABASE_KEY"])
    ok = True
    for p in pls:
        ok = (send_to_demo(demo, p) is not None) and ok
    return ok


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="every week on/after this date (YYYY-MM-DD); default = latest week")
    ap.add_argument("--until", help="last date for --since (YYYY-MM-DD); default today")
    ap.add_argument("--dry-run", action="store_true", help="print the exact door payloads, send nothing")
    args = ap.parse_args()
    since = date.fromisoformat(args.since) if args.since else None
    until = date.fromisoformat(args.until) if args.until else None
    if args.dry_run:
        print(json.dumps(payloads(since, until), indent=2))
        return
    if not (os.getenv("DEMO_SUPABASE_URL") and os.getenv("DEMO_SUPABASE_KEY")):
        raise SystemExit("set DEMO_SUPABASE_URL and DEMO_SUPABASE_KEY")
    raise SystemExit(0 if sync(since, until) else 1)


if __name__ == "__main__":
    main()
