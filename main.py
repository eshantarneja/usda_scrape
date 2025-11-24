"""Main orchestration script for USDA scraper pipeline."""
import os
import logging
import argparse
import requests
from datetime import datetime
from pdf_parser import PDFParser
from database import DatabaseManager
from config import REPORTS_CONFIG

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class USDAScraperPipeline:
    """Main pipeline to orchestrate scraping, parsing, and storing USDA reports."""

    def __init__(self):
        """Initialize the pipeline."""
        self.db = DatabaseManager()
        self.temp_dir = os.path.join(os.path.dirname(__file__), 'temp')

        # Create temp directory if it doesn't exist
        os.makedirs(self.temp_dir, exist_ok=True)

    def download_pdf(self, url: str, destination: str) -> bool:
        """Download PDF from URL.

        Args:
            url: URL of PDF to download
            destination: Path to save the PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(destination, 'wb') as f:
                f.write(response.content)

            logger.info(f"Successfully downloaded PDF to {destination}")
            return True
        except Exception as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            return False

    def extract_pdf_date(self, pdf_path: str) -> str:
        """Extract date from PDF content.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Date string in YYYY-MM-DD format
        """
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                # Get first page text
                first_page = pdf.pages[0]
                text = first_page.extract_text()

                # Look for date patterns like "November 21, 2025"
                import re
                date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})'
                match = re.search(date_pattern, text)

                if match:
                    month_name, day, year = match.groups()
                    month_map = {
                        'January': 1, 'February': 2, 'March': 3, 'April': 4,
                        'May': 5, 'June': 6, 'July': 7, 'August': 8,
                        'September': 9, 'October': 10, 'November': 11, 'December': 12
                    }
                    month = month_map[month_name]
                    date_obj = datetime(int(year), month, int(day))
                    return date_obj.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"Could not extract date from PDF: {e}")

        # Fallback to today's date
        return datetime.now().strftime('%Y-%m-%d')

    def process_report(self, report_type: str, force: bool = False) -> bool:
        """Process a single report type.

        Args:
            report_type: Type of report to process (e.g., 'branded_beef')
            force: Force processing even if report already exists

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing report type: {report_type}")

        try:
            # Step 1: Get report configuration
            if report_type not in REPORTS_CONFIG:
                logger.error(f"Unknown report type: {report_type}")
                return False

            report_config = REPORTS_CONFIG[report_type]
            pdf_url = report_config['pdf_url']

            logger.info(f"Step 1: Downloading PDF from {pdf_url}")

            # Step 2: Download PDF to temp location
            pdf_filename = f"{report_type}_temp.pdf"
            pdf_path = os.path.join(self.temp_dir, pdf_filename)

            if not self.download_pdf(pdf_url, pdf_path):
                logger.error("Failed to download PDF")
                return False

            # Step 3: Extract date from PDF
            logger.info("Step 2: Extracting report date from PDF")
            report_date_str = self.extract_pdf_date(pdf_path)
            logger.info(f"Report date: {report_date_str}")

            # Step 4: Check if report already exists in database
            if not force and self.db.check_report_exists(report_type, report_date_str):
                logger.info(f"Report already exists for {report_type} on {report_date_str}. Skipping.")
                os.remove(pdf_path)
                return True

            # Step 5: Create report record in database
            logger.info("Step 3: Creating report record in database")
            report_id = self.db.insert_report({
                'report_type': report_type,
                'report_date': report_date_str,
                'pdf_url': pdf_url
            })

            if not report_id:
                logger.error("Failed to create report record in database")
                os.remove(pdf_path)
                return False

            # Rename PDF with actual date
            final_pdf_filename = f"{report_type}_{report_date_str}.pdf"
            final_pdf_path = os.path.join(self.temp_dir, final_pdf_filename)
            os.rename(pdf_path, final_pdf_path)
            pdf_path = final_pdf_path

            # Step 6: Parse PDF
            logger.info("Step 4: Parsing PDF")
            try:
                parser = PDFParser(pdf_path)
                pricing_data = parser.parse(report_type)

                if not pricing_data:
                    logger.warning("No pricing data extracted from PDF")
                    self.db.update_report_status(report_id, 'completed', 'No data found in PDF')
                    return True

                logger.info(f"Extracted {len(pricing_data)} pricing records")

            except Exception as e:
                logger.error(f"Error parsing PDF: {e}")
                self.db.update_report_status(report_id, 'failed', f'PDF parsing error: {str(e)}')
                return False

            # Step 7: Save to database
            logger.info("Step 5: Saving pricing data to database")
            success_count = self.db.save_pricing_data(
                report_id=report_id,
                report_date=report_date_str,
                report_type=report_type,
                pricing_data=pricing_data
            )

            # Step 8: Update report status
            if success_count > 0:
                self.db.update_report_status(report_id, 'completed')
                logger.info(f"Successfully processed report. Saved {success_count} price records.")
            else:
                self.db.update_report_status(report_id, 'failed', 'No pricing data saved')
                logger.error("Failed to save any pricing data")
                return False

            # Step 9: Cleanup
            try:
                os.remove(pdf_path)
                logger.info("Cleaned up temporary PDF file")
            except Exception as e:
                logger.warning(f"Failed to delete temporary PDF: {e}")

            return True

        except Exception as e:
            logger.error(f"Unexpected error processing report: {e}", exc_info=True)
            return False

    def run(self, report_types: list, force: bool = False):
        """Run the pipeline for multiple report types.

        Args:
            report_types: List of report types to process
            force: Force processing even if reports already exist
        """
        logger.info(f"Starting USDA scraper pipeline for {len(report_types)} report type(s)")

        results = {}
        for report_type in report_types:
            success = self.process_report(report_type, force)
            results[report_type] = success

        # Summary
        logger.info("\n" + "="*50)
        logger.info("Pipeline execution summary:")
        for report_type, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            logger.info(f"  {report_type}: {status}")
        logger.info("="*50)

        # Return overall success (all reports processed successfully)
        return all(results.values())


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='USDA Meat Product Price Scraper')

    parser.add_argument(
        '--reports',
        nargs='+',
        default=['branded_beef', 'ungraded_beef'],
        help='Report types to process (default: branded_beef ungraded_beef)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force processing even if report already exists'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--calculate-metrics',
        action='store_true',
        help='Calculate USDA metrics after scraping'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run pipeline
    pipeline = USDAScraperPipeline()
    success = pipeline.run(args.reports, args.force)

    # Calculate metrics if requested
    if args.calculate_metrics and success:
        logger.info("Starting metrics calculation...")
        from calculate_metrics import MetricsCalculator
        calculator = MetricsCalculator()
        metrics_count = calculator.calculate_all_metrics()
        logger.info(f"Metrics calculation complete. Created {metrics_count} metric records.")

    # Exit with appropriate code
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
