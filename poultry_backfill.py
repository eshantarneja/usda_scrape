"""Backfill the weekly chicken / turkey reports from the ESMIS archive.

The mnreports PDF (config REPORTS_CONFIG[...]['pdf_url']) is the latest week only.
Every past week is listed, newest first, at
  https://esmis.nal.usda.gov/publication/<esmis_slug>?page=N
with one AMS_3646.PDF / AMS_3647.PDF link per week. This walks those pages and
runs each PDF through the normal pipeline (main.USDAScraperPipeline.process_report
with that week's URL), so a backfilled week lands in usda_reports / usda_prices
exactly as a scraped one does, with the archive URL as its pdf_url. Weeks already
in the database are skipped by the pipeline. The Demo sync is a separate step:
  python demo_sync.py --type weekly_chicken --type weekly_turkey --since 2025-01-01

  python poultry_backfill.py --dry-run                      # list the archive links
  python poultry_backfill.py --since 2025-10-01             # both reports, back to that week
  python poultry_backfill.py --report weekly_turkey --pages 3
"""
import argparse
import logging
import os
import re
from datetime import date
from typing import List

import requests

from config import REPORTS_CONFIG

logger = logging.getLogger(__name__)

ESMIS = "https://esmis.nal.usda.gov"
POULTRY_TYPES = ("weekly_chicken", "weekly_turkey")
_LINK = re.compile(r'href="(/sites/default/release-files/[^"]+/AMS_36(?:46|47)\.PDF)"')


def archive_links(report_type: str, pages: int, timeout: int = 60) -> List[str]:
    """Every week's PDF URL on the first `pages` listing pages, newest first, de-duplicated."""
    slug = REPORTS_CONFIG[report_type]["esmis_slug"]
    seen, out = set(), []
    for page in range(pages):
        resp = requests.get(f"{ESMIS}/publication/{slug}", params={"page": page}, timeout=timeout)
        if resp.status_code != 200:
            logger.warning(f"{report_type}: listing page {page} returned {resp.status_code}; stopping")
            break
        links = _LINK.findall(resp.text)
        if not links:
            break
        for rel in links:
            if rel not in seen:
                seen.add(rel)
                out.append(ESMIS + rel)
    return out


def backfill(report_type: str, pages: int, since: date = None, dry_run: bool = False) -> bool:
    links = archive_links(report_type, pages)
    logger.info(f"{report_type}: {len(links)} archive link(s) on {pages} page(s)")
    if dry_run:
        for u in links:
            logger.info(f"DRY {report_type} {u}")
        return True

    from main import USDAScraperPipeline
    pipeline = USDAScraperPipeline()
    ok = True
    for url in links:          # newest first; stop once a week is older than --since
        local = os.path.join(pipeline.temp_dir, f"{report_type}_peek.pdf")
        if not pipeline.download_pdf(url, local):
            logger.error(f"{report_type}: could not download {url}")
            ok = False
            continue
        report_date = pipeline.extract_pdf_date(local)
        os.remove(local)
        if since and date.fromisoformat(report_date) < since:
            logger.info(f"{report_type}: {report_date} is before {since}; done")
            break
        if not pipeline.process_report(report_type, force=False, pdf_url=url):
            ok = False
    return ok


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", choices=POULTRY_TYPES, action="append", help="one report (repeatable); default both")
    ap.add_argument("--since", help="stop at the first week before this date (YYYY-MM-DD)")
    ap.add_argument("--pages", type=int, default=17, help="ESMIS listing pages to walk (10 weeks each)")
    ap.add_argument("--dry-run", action="store_true", help="list the archive links, download and write nothing")
    args = ap.parse_args()
    since = date.fromisoformat(args.since) if args.since else None
    ok = True
    for rt in (args.report or POULTRY_TYPES):
        ok = backfill(rt, args.pages, since, args.dry_run) and ok
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
