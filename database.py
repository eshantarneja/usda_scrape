"""Module to handle Supabase database operations."""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manager for Supabase database operations."""

    def __init__(self):
        """Initialize the database manager."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")

    def insert_report(self, report_data: Dict) -> Optional[str]:
        """Insert a new report record or get existing one.

        Args:
            report_data: Dictionary containing report metadata

        Returns:
            Report ID (UUID) or None if operation failed
        """
        try:
            # Check if report already exists
            existing = self.client.table('usda_reports').select('id').eq(
                'report_type', report_data['report_type']
            ).eq(
                'report_date', report_data['report_date']
            ).execute()

            if existing.data and len(existing.data) > 0:
                report_id = existing.data[0]['id']
                logger.info(f"Report already exists with ID: {report_id}")
                return report_id

            # Determine category based on report_type
            category = 'pork' if report_data['report_type'] == 'pork_cuts' else 'beef'

            # Insert new report
            result = self.client.table('usda_reports').insert({
                'report_type': report_data['report_type'],
                'report_date': report_data['report_date'],
                'pdf_url': report_data['pdf_url'],
                'status': 'processing',
                'category': category
            }).execute()

            if result.data and len(result.data) > 0:
                report_id = result.data[0]['id']
                logger.info(f"Inserted new report with ID: {report_id}")
                return report_id
            else:
                logger.error("Failed to insert report - no data returned")
                return None

        except Exception as e:
            logger.error(f"Error inserting report: {e}")
            return None

    def update_report_status(self, report_id: str, status: str, error_message: Optional[str] = None):
        """Update the status of a report.

        Args:
            report_id: UUID of the report
            status: New status (e.g., 'completed', 'failed')
            error_message: Optional error message if status is 'failed'
        """
        try:
            update_data = {'status': status}
            if error_message:
                update_data['error_message'] = error_message

            self.client.table('usda_reports').update(update_data).eq('id', report_id).execute()
            logger.info(f"Updated report {report_id} status to: {status}")

        except Exception as e:
            logger.error(f"Error updating report status: {e}")

    def upsert_product(self, product_data: Dict) -> Optional[str]:
        """Insert or update a product record.

        Products are now unique by product_name only (no report_type or category).
        Category field stores meat type ('beef' or 'pork').

        Args:
            product_data: Dictionary containing product information
                - product_name: Name of the product
                - product_code: IMPS code (optional, None for pork)
                - category: Meat type ('beef' or 'pork')

        Returns:
            Product ID (UUID) or None if operation failed
        """
        try:
            # Check if product already exists by product_name only
            # Try with category column first, fall back to without if column doesn't exist
            try:
                existing = self.client.table('usda_products').select('id, category').eq(
                    'product_name', product_data['product_name']
                ).execute()
                has_category_column = True
            except Exception:
                existing = self.client.table('usda_products').select('id').eq(
                    'product_name', product_data['product_name']
                ).execute()
                has_category_column = False

            if existing.data and len(existing.data) > 0:
                product_id = existing.data[0]['id']

                # Update category if column exists and it's not set
                if has_category_column:
                    existing_category = existing.data[0].get('category')
                    if not existing_category and product_data.get('category'):
                        try:
                            self.client.table('usda_products').update({
                                'category': product_data['category']
                            }).eq('id', product_id).execute()
                            logger.debug(f"Updated product {product_id} with category: {product_data['category']}")
                        except Exception:
                            pass  # Category column might not exist

                logger.debug(f"Product already exists with ID: {product_id}")
                return product_id

            # Insert new product
            insert_data = {
                'product_name': product_data['product_name'],
                'product_code': product_data.get('product_code')
            }
            # Only include category if column exists
            if has_category_column and product_data.get('category'):
                insert_data['category'] = product_data['category']

            result = self.client.table('usda_products').insert(insert_data).execute()

            if result.data and len(result.data) > 0:
                product_id = result.data[0]['id']
                logger.debug(f"Inserted new product with ID: {product_id}")
                return product_id
            else:
                logger.error(f"Failed to insert product: {product_data['product_name']}")
                return None

        except Exception as e:
            logger.error(f"Error upserting product: {e}")
            return None

    def insert_price(self, price_data: Dict) -> bool:
        """Insert a price record.

        Args:
            price_data: Dictionary containing price information

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if price already exists for this product, date, category, and report_type
            query = self.client.table('usda_prices').select('id').eq(
                'product_id', price_data['product_id']
            ).eq(
                'report_date', price_data['report_date']
            )

            # Add category and report_type filters
            if price_data.get('category'):
                query = query.eq('category', price_data['category'])
            if price_data.get('report_type'):
                query = query.eq('report_type', price_data['report_type'])

            existing = query.execute()

            if existing.data and len(existing.data) > 0:
                # Update existing price
                result = self.client.table('usda_prices').update({
                    'price': price_data.get('price'),
                    'low_price': price_data.get('low_price'),
                    'high_price': price_data.get('high_price'),
                    'volume': price_data.get('volume'),
                    'unit': price_data.get('unit'),
                    'category': price_data.get('category'),
                    'report_type': price_data.get('report_type'),
                    'additional_data': price_data.get('additional_data', {})
                }).eq('id', existing.data[0]['id']).execute()
                logger.debug(f"Updated existing price record")
            else:
                # Insert new price
                result = self.client.table('usda_prices').insert({
                    'product_id': price_data['product_id'],
                    'report_id': price_data['report_id'],
                    'report_date': price_data['report_date'],
                    'price': price_data.get('price'),
                    'low_price': price_data.get('low_price'),
                    'high_price': price_data.get('high_price'),
                    'volume': price_data.get('volume'),
                    'unit': price_data.get('unit', 'USD'),
                    'category': price_data.get('category'),
                    'report_type': price_data.get('report_type'),
                    'additional_data': price_data.get('additional_data', {})
                }).execute()
                logger.debug(f"Inserted new price record")

            return True

        except Exception as e:
            logger.error(f"Error inserting price: {e}")
            return False

    def save_pricing_data(self, report_id: str, report_date: str,
                         report_type: str, pricing_data: List[Dict]) -> int:
        """Save all pricing data from a report.

        Args:
            report_id: UUID of the report
            report_date: Date of the report
            report_type: Type of report
            pricing_data: List of pricing data dictionaries

        Returns:
            Number of successfully inserted price records
        """
        success_count = 0

        # Determine meat type based on report_type
        meat_type = 'pork' if report_type == 'pork_cuts' else 'beef'

        for record in pricing_data:
            # First, ensure the product exists with meat type category
            product_id = self.upsert_product({
                'product_name': record['product_name'],
                'product_code': record.get('product_code'),
                'category': meat_type
            })

            if not product_id:
                logger.warning(f"Failed to get product ID for: {record['product_name']}")
                continue

            # Insert the price record (with category and report_type)
            price_record = {
                'product_id': product_id,
                'report_id': report_id,
                'report_date': report_date,
                'price': record.get('price'),
                'low_price': record.get('low_price'),
                'high_price': record.get('high_price'),
                'volume': record.get('volume'),
                'unit': 'USD',
                'category': record.get('category'),
                'report_type': report_type,
                'additional_data': record.get('additional_data', {})
            }

            if self.insert_price(price_record):
                success_count += 1

        logger.info(f"Successfully saved {success_count}/{len(pricing_data)} price records")
        return success_count

    def get_latest_report_date(self, report_type: str) -> Optional[datetime]:
        """Get the date of the most recent report for a given type.

        Args:
            report_type: Type of report to query

        Returns:
            Date of the most recent report, or None if no reports exist
        """
        try:
            result = self.client.table('usda_reports').select('report_date').eq(
                'report_type', report_type
            ).order('report_date', desc=True).limit(1).execute()

            if result.data and len(result.data) > 0:
                return datetime.fromisoformat(result.data[0]['report_date'])
            return None

        except Exception as e:
            logger.error(f"Error getting latest report date: {e}")
            return None

    def check_report_exists(self, report_type: str, report_date: str) -> bool:
        """Check if a report already exists in the database.

        Args:
            report_type: Type of report
            report_date: Date of report

        Returns:
            True if report exists, False otherwise
        """
        try:
            result = self.client.table('usda_reports').select('id').eq(
                'report_type', report_type
            ).eq(
                'report_date', report_date
            ).execute()

            return result.data and len(result.data) > 0

        except Exception as e:
            logger.error(f"Error checking if report exists: {e}")
            return False


if __name__ == "__main__":
    # Example usage
    db = DatabaseManager()

    # Test connection
    print("Database manager initialized successfully")

    # Check latest report
    latest = db.get_latest_report_date('branded_beef')
    if latest:
        print(f"Latest branded_beef report date: {latest}")
    else:
        print("No reports found for branded_beef")
