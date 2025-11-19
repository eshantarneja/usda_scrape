"""Module to scrape USDA meat product reports."""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import logging
from typing import List, Dict, Optional
from config import USDA_BASE_URL, USDA_REPORTS_PAGE, REPORTS_CONFIG

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class USDAScraper:
    """Scraper for USDA meat product reports."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; USDA-Scraper/1.0)'
        })

    def fetch_reports_page(self) -> str:
        """Fetch the main reports listing page.

        Returns:
            HTML content of the reports page
        """
        try:
            response = self.session.get(USDA_REPORTS_PAGE, timeout=30)
            response.raise_for_status()
            logger.info(f"Successfully fetched reports page: {USDA_REPORTS_PAGE}")
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching reports page: {e}")
            raise

    def parse_report_links(self, html: str, report_types: List[str]) -> List[Dict]:
        """Parse the HTML to find PDF links for target reports.

        Args:
            html: HTML content of the reports page
            report_types: List of report type keys to look for (e.g., ['branded_beef'])

        Returns:
            List of dicts containing report metadata
        """
        soup = BeautifulSoup(html, 'html.parser')
        reports = []

        # Find all links on the page
        for report_type in report_types:
            report_config = REPORTS_CONFIG.get(report_type)
            if not report_config:
                logger.warning(f"Unknown report type: {report_type}")
                continue

            report_name = report_config['name']
            logger.info(f"Looking for report: {report_name}")

            # Search for the report by name in the page
            # USDA reports are typically organized in sections with links
            links = soup.find_all('a', href=re.compile(r'\.pdf$', re.IGNORECASE))

            for link in links:
                link_text = link.get_text(strip=True)
                parent_text = link.parent.get_text(strip=True) if link.parent else ""

                # Check if this link matches our target report
                if report_name.lower() in link_text.lower() or report_name.lower() in parent_text.lower():
                    pdf_url = link.get('href')

                    # Make URL absolute if it's relative
                    if pdf_url.startswith('/'):
                        pdf_url = f"{USDA_BASE_URL}{pdf_url}"
                    elif not pdf_url.startswith('http'):
                        pdf_url = f"{USDA_BASE_URL}/{pdf_url}"

                    # Extract date from URL or link text
                    report_date = self._extract_date_from_url(pdf_url, link_text)

                    reports.append({
                        'report_type': report_type,
                        'report_name': report_name,
                        'pdf_url': pdf_url,
                        'report_date': report_date,
                        'link_text': link_text
                    })

                    logger.info(f"Found report: {link_text} - {pdf_url}")
                    break  # Found the report, move to next type

        return reports

    def _extract_date_from_url(self, url: str, link_text: str) -> Optional[datetime]:
        """Extract date from PDF URL or link text.

        Args:
            url: PDF URL
            link_text: Text of the link

        Returns:
            datetime object or None if date cannot be extracted
        """
        # Try to extract date from URL (e.g., ams_2457.pdf might have date embedded)
        # Common patterns: YYYYMMDD, MMDDYY, etc.
        date_patterns = [
            r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})',  # YYYY-MM-DD or YYYYMMDD
            r'(\d{2})[-_]?(\d{2})[-_]?(\d{4})',  # MM-DD-YYYY or MMDDYYYY
            r'(\d{2})[-_]?(\d{2})[-_]?(\d{2})',  # MM-DD-YY or MMDDYY
        ]

        for pattern in date_patterns:
            match = re.search(pattern, url)
            if match:
                groups = match.groups()
                try:
                    # Try different date formats
                    if len(groups[0]) == 4:  # YYYY-MM-DD
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                    elif len(groups[2]) == 4:  # MM-DD-YYYY
                        return datetime(int(groups[2]), int(groups[0]), int(groups[1]))
                    else:  # MM-DD-YY
                        year = 2000 + int(groups[2]) if int(groups[2]) < 50 else 1900 + int(groups[2])
                        return datetime(year, int(groups[0]), int(groups[1]))
                except (ValueError, IndexError):
                    continue

        # Try to extract from link text
        match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', link_text)
        if match:
            try:
                month, day, year = match.groups()
                year = int(year)
                if year < 100:
                    year = 2000 + year if year < 50 else 1900 + year
                return datetime(year, int(month), int(day))
            except (ValueError, IndexError):
                pass

        # If we can't extract a date, use today's date as a fallback
        logger.warning(f"Could not extract date from URL or link text, using today's date")
        return datetime.now()

    def download_pdf(self, url: str, save_path: str) -> bool:
        """Download a PDF from the given URL.

        Args:
            url: URL of the PDF
            save_path: Path to save the downloaded PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Successfully downloaded PDF to {save_path}")
            return True
        except requests.RequestException as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            return False

    def get_latest_reports(self, report_types: List[str]) -> List[Dict]:
        """Get the latest reports for the specified types.

        Args:
            report_types: List of report type keys to fetch

        Returns:
            List of report metadata dictionaries
        """
        html = self.fetch_reports_page()
        reports = self.parse_report_links(html, report_types)
        return reports


if __name__ == "__main__":
    # Example usage
    scraper = USDAScraper()
    reports = scraper.get_latest_reports(['branded_beef', 'ungraded_beef'])

    for report in reports:
        print(f"\nReport Type: {report['report_type']}")
        print(f"Report Name: {report['report_name']}")
        print(f"PDF URL: {report['pdf_url']}")
        print(f"Report Date: {report['report_date']}")
