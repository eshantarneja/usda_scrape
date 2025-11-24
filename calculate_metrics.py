"""Script to calculate USDA price metrics and populate usda_metrics table."""
import logging
from datetime import datetime, timedelta
from database import DatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculator for USDA price metrics."""

    def __init__(self):
        """Initialize the calculator."""
        self.db = DatabaseManager()

    def calculate_all_metrics(self) -> int:
        """Calculate metrics for all product/category/report_type combinations.

        Returns:
            Number of metric records created
        """
        logger.info("Starting metrics calculation")

        # Step 1: Truncate existing metrics
        logger.info("Truncating existing metrics data")
        self.db.client.table('usda_metrics').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

        # Step 2: Get all prices and extract unique combinations
        all_prices = self.db.client.table('usda_prices').select(
            'product_id, category, report_type'
        ).not_.is_('product_id', 'null').execute()

        # Extract unique combinations
        seen = set()
        combinations = []
        for row in all_prices.data:
            key = (row['product_id'], row.get('category'), row['report_type'])
            if key not in seen:
                seen.add(key)
                combinations.append({
                    'product_id': row['product_id'],
                    'category': row.get('category'),
                    'report_type': row['report_type']
                })

        logger.info(f"Found {len(combinations)} unique product/category/report_type combinations")

        # Step 3: Calculate metrics for each combination
        metrics_created = 0
        for combo in combinations:
            product_id = combo['product_id']
            category = combo['category']
            report_type = combo['report_type']

            try:
                metric_data = self._calculate_metric(product_id, category, report_type)
                if metric_data:
                    self._insert_metric(metric_data)
                    metrics_created += 1
            except Exception as e:
                logger.error(f"Error calculating metric for product {product_id}, category {category}, report_type {report_type}: {e}")
                continue

        logger.info(f"Metrics calculation complete. Created {metrics_created} metric records.")
        return metrics_created

    def _calculate_metric(self, product_id: str, category: str, report_type: str) -> dict:
        """Calculate metrics for a single product/category/report_type combination.

        Args:
            product_id: UUID of the product
            category: Category name
            report_type: Report type

        Returns:
            Dictionary with calculated metrics or None if no data
        """
        # Get the most recent price
        query = self.db.client.table('usda_prices').select('price, report_date').eq(
            'product_id', product_id
        ).eq('report_type', report_type)

        if category:
            query = query.eq('category', category)

        recent = query.order('report_date', desc=True).limit(1).execute()

        if not recent.data or len(recent.data) == 0:
            return None

        last_price = float(recent.data[0]['price']) if recent.data[0]['price'] else None
        last_price_date = recent.data[0]['report_date']

        if not last_price or not last_price_date:
            return None

        # Parse last_price_date
        last_date = datetime.strptime(last_price_date, '%Y-%m-%d').date()

        # Calculate 7-day lookback date
        date_7d_ago = last_date - timedelta(days=7)
        price_7d_ago = self._get_price_on_or_before(product_id, category, report_type, date_7d_ago)

        # Calculate 30-day lookback date
        date_30d_ago = last_date - timedelta(days=30)
        price_30d_ago = self._get_price_on_or_before(product_id, category, report_type, date_30d_ago)

        # Calculate changes
        change_7d = None
        change_7d_pct = None
        if price_7d_ago:
            change_7d = last_price - price_7d_ago
            change_7d_pct = (change_7d / price_7d_ago) * 100 if price_7d_ago != 0 else None

        change_30d = None
        change_30d_pct = None
        if price_30d_ago:
            change_30d = last_price - price_30d_ago
            change_30d_pct = (change_30d / price_30d_ago) * 100 if price_30d_ago != 0 else None

        return {
            'product_id': product_id,
            'category': category,
            'report_type': report_type,
            'calculation_date': datetime.now().date().isoformat(),
            'last_price': last_price,
            'last_price_date': last_price_date,
            'price_7d_ago': price_7d_ago,
            'change_7d': change_7d,
            'change_7d_pct': change_7d_pct,
            'price_30d_ago': price_30d_ago,
            'change_30d': change_30d,
            'change_30d_pct': change_30d_pct
        }

    def _get_price_on_or_before(self, product_id: str, category: str, report_type: str, target_date) -> float:
        """Get the price on or before a target date.

        Args:
            product_id: UUID of the product
            category: Category name
            report_type: Report type
            target_date: Target date to look back to

        Returns:
            Price as float or None if not found
        """
        query = self.db.client.table('usda_prices').select('price').eq(
            'product_id', product_id
        ).eq('report_type', report_type).lte(
            'report_date', target_date.isoformat()
        )

        if category:
            query = query.eq('category', category)

        result = query.order('report_date', desc=True).limit(1).execute()

        if result.data and len(result.data) > 0 and result.data[0]['price']:
            return float(result.data[0]['price'])

        return None

    def _insert_metric(self, metric_data: dict):
        """Insert a metric record into the database.

        Args:
            metric_data: Dictionary containing metric data
        """
        self.db.client.table('usda_metrics').insert(metric_data).execute()
        logger.debug(f"Inserted metric for product {metric_data['product_id']}, category {metric_data['category']}, report_type {metric_data['report_type']}")


def main():
    """Main entry point."""
    calculator = MetricsCalculator()
    metrics_created = calculator.calculate_all_metrics()
    logger.info(f"Metrics calculation completed successfully. Created {metrics_created} records.")


if __name__ == "__main__":
    main()
