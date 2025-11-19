"""Main orchestration script for USDA scraper pipeline."""
import os
import logging
import argparse
from datetime import datetime
from scraper import USDAScraper
from pdf_parser import PDFParser
from database import DatabaseManager

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
        self.scraper = USDAScraper()
        self.db = DatabaseManager()
        self.temp_dir = os.path.join(os.path.dirname(__file__), 'temp')

        # Create temp directory if it doesn't exist
        os.makedirs(self.temp_dir, exist_ok=True)

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
            # Step 1: Scrape to find the latest report
            logger.info("Step 1: Fetching latest report information")
            reports = self.scraper.get_latest_reports([report_type])

            if not reports:
                logger.error(f"No reports found for type: {report_type}")
                return False

            report_info = reports[0]
            pdf_url = report_info['pdf_url']
            report_date = report_info['report_date']

            # Convert datetime to date string
            if isinstance(report_date, datetime):
                report_date_str = report_date.strftime('%Y-%m-%d')
            else:
                report_date_str = str(report_date)

            logger.info(f"Found report: {pdf_url} (Date: {report_date_str})")

            # Step 2: Check if report already exists in database
            if not force and self.db.check_report_exists(report_type, report_date_str):
                logger.info(f"Report already exists for {report_type} on {report_date_str}. Skipping.")
                return True

            # Step 3: Create report record in database
            logger.info("Step 2: Creating report record in database")
            report_id = self.db.insert_report({
                'report_type': report_type,
                'report_date': report_date_str,
                'pdf_url': pdf_url
            })

            if not report_id:
                logger.error("Failed to create report record in database")
                return False

            # Step 4: Download PDF
            logger.info("Step 3: Downloading PDF")
            pdf_filename = f"{report_type}_{report_date_str}.pdf"
            pdf_path = os.path.join(self.temp_dir, pdf_filename)

            if not self.scraper.download_pdf(pdf_url, pdf_path):
                self.db.update_report_status(report_id, 'failed', 'Failed to download PDF')
                return False

            # Step 5: Parse PDF
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

            # Step 6: Save to database
            logger.info("Step 5: Saving pricing data to database")
            success_count = self.db.save_pricing_data(
                report_id=report_id,
                report_date=report_date_str,
                report_type=report_type,
                pricing_data=pricing_data
            )

            # Step 7: Update report status
            if success_count > 0:
                self.db.update_report_status(report_id, 'completed')
                logger.info(f"Successfully processed report. Saved {success_count} price records.")
            else:
                self.db.update_report_status(report_id, 'failed', 'No pricing data saved')
                logger.error("Failed to save any pricing data")
                return False

            # Step 8: Cleanup
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

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run pipeline
    pipeline = USDAScraperPipeline()
    success = pipeline.run(args.reports, args.force)

    # Exit with appropriate code
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
