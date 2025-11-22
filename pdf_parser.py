"""Module to parse USDA PDF reports and extract pricing data."""
import pdfplumber
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFParser:
    """Parser for USDA meat product PDF reports."""

    def __init__(self, pdf_path: str):
        """Initialize the parser with a PDF file path.

        Args:
            pdf_path: Path to the PDF file to parse
        """
        self.pdf_path = pdf_path

    def extract_text_lines(self) -> List[str]:
        """Extract all text lines from the PDF.

        Returns:
            List of text lines from all pages
        """
        all_lines = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                logger.info(f"Opened PDF with {len(pdf.pages)} pages")

                for page_num, page in enumerate(pdf.pages, start=1):
                    logger.info(f"Processing page {page_num}")

                    # Extract text from the page
                    text = page.extract_text()

                    if text:
                        lines = text.split('\n')
                        logger.info(f"Extracted {len(lines)} lines from page {page_num}")
                        all_lines.extend(lines)
                    else:
                        logger.warning(f"No text found on page {page_num}")

                return all_lines
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise

    def parse_pricing_data(self, lines: List[str], report_type: str) -> List[Dict]:
        """Parse pricing data from extracted text lines.

        For branded_beef: Extracts from "Upper 2/3 Choice Items Cuts" section
        For ungraded_beef: Extracts from "Ungraded Cuts, Fat Limitations 1-6" section
        For daily_afternoon: Extracts from multiple sections (Choice, Select, Mixed, Ground Beef)

        Args:
            lines: List of text lines extracted from PDF
            report_type: Type of report being parsed

        Returns:
            List of dictionaries containing product pricing data
        """
        if report_type == 'daily_afternoon':
            return self._parse_daily_report(lines, report_type)
        else:
            return self._parse_weekly_report(lines, report_type)

    def _parse_weekly_report(self, lines: List[str], report_type: str) -> List[Dict]:
        """Parse weekly report with single target section."""
        pricing_data = []
        in_target_section = False
        current_category = None

        # Determine which section to look for based on report type
        if report_type == 'branded_beef':
            target_section_keywords = ['upper 2/3 choice', 'items cuts']
            section_category = 'Upper 2/3 Choice'
            end_keywords = ['lower', 'branded select']
        elif report_type == 'ungraded_beef':
            target_section_keywords = ['ungraded cuts', 'fat limitations']
            section_category = 'Ungraded Cuts'
            end_keywords = ['branded', 'choice']
        else:
            logger.warning(f"Unknown report type: {report_type}")
            return pricing_data

        logger.info(f"Processing {len(lines)} lines for {report_type}")

        for line_idx, line in enumerate(lines):
            line_lower = line.lower().strip()

            # Check if we've entered the target section
            if all(keyword in line_lower for keyword in target_section_keywords):
                in_target_section = True
                current_category = section_category
                logger.info(f"Found target section at line {line_idx}: {line}")
                continue

            # Check if we've left the target section
            if in_target_section and any(keyword in line_lower for keyword in end_keywords):
                logger.info(f"Reached end of {section_category} section at line {line_idx}")
                break

            # Skip if not in target section
            if not in_target_section:
                continue

            # Skip header rows and empty lines
            if not line.strip() or self._is_header_row(line):
                continue

            # Parse data line
            parsed = self._parse_data_line(line)

            if parsed:
                imps_code = parsed['imps_code']
                subprimal = parsed['description']
                trades = parsed['trades']
                pounds = parsed['pounds']
                low_price = parsed['low_price']
                high_price = parsed['high_price']
                weighted_avg = parsed['weighted_avg']

                # Combine IMPS code and subprimal description for product name
                product_name = f"{imps_code} - {subprimal}"

                # Create pricing record
                pricing_record = {
                    'product_name': product_name,
                    'product_code': imps_code,
                    'price': weighted_avg,
                    'low_price': low_price,
                    'high_price': high_price,
                    'volume': pounds,
                    'report_type': report_type,
                    'category': current_category,
                    'additional_data': {
                        'num_trades': trades,
                        'imps_code': imps_code,
                        'sub_primal': subprimal
                    }
                }

                pricing_data.append(pricing_record)
                logger.debug(f"Parsed: {product_name} - Avg: ${weighted_avg}, Range: ${low_price}-${high_price}, Volume: {pounds} lbs, Trades: {trades}")

        logger.info(f"Extracted {len(pricing_data)} pricing records from {section_category if pricing_data else 'target'} section")
        return pricing_data

    def _parse_daily_report(self, lines: List[str], report_type: str) -> List[Dict]:
        """Parse daily report with multiple sections."""
        pricing_data = []
        current_section = None

        # Section markers for daily report
        section_markers = {
            'Choice Cuts': ('choice cuts', 'fat limitations'),
            'Select Cuts': ('select cuts', 'fat limitations'),
            'Choice, Select & Ungraded': ('choice, select & ungraded', 'fat limitations'),
            'Ground Beef': ('gb - steer/heifer source', '10 pound chub')
        }

        logger.info(f"Processing {len(lines)} lines for daily report")

        for line_idx, line in enumerate(lines):
            line_lower = line.lower().strip()

            # Check which section we're in
            for section_name, keywords in section_markers.items():
                if all(kw in line_lower for kw in keywords):
                    current_section = section_name
                    logger.info(f"Found section at line {line_idx}: {section_name}")
                    continue

            # Skip if not in any section
            if not current_section:
                continue

            # Skip header rows and empty lines
            if not line.strip() or self._is_header_row(line):
                continue

            # Parse based on section type
            if current_section == 'Ground Beef':
                parsed = self._parse_ground_beef_line(line)
            else:
                parsed = self._parse_data_line(line)

            if parsed:
                if current_section == 'Ground Beef':
                    # Ground beef format: no IMPS code
                    product_name = parsed['product_name']
                    imps_code = None
                else:
                    # Standard format with IMPS code
                    imps_code = parsed['imps_code']
                    subprimal = parsed['description']
                    product_name = f"{imps_code} - {subprimal}"

                trades = parsed['trades']
                pounds = parsed['pounds']
                low_price = parsed.get('low_price')
                high_price = parsed.get('high_price')
                weighted_avg = parsed.get('weighted_avg')

                # Create pricing record
                pricing_record = {
                    'product_name': product_name,
                    'product_code': imps_code,
                    'price': weighted_avg,
                    'low_price': low_price,
                    'high_price': high_price,
                    'volume': pounds,
                    'report_type': report_type,
                    'category': current_section,
                    'additional_data': {
                        'num_trades': trades,
                        'imps_code': imps_code,
                        'sub_primal': subprimal if current_section != 'Ground Beef' else product_name
                    }
                }

                pricing_data.append(pricing_record)
                logger.debug(f"Parsed: {product_name} - Avg: ${weighted_avg}, Range: ${low_price}-${high_price}, Volume: {pounds} lbs, Trades: {trades}")

        logger.info(f"Extracted {len(pricing_data)} pricing records from daily report")
        return pricing_data

    def _parse_data_line(self, line: str) -> Optional[Dict]:
        """Parse a single data line into components.

        Args:
            line: Text line to parse

        Returns:
            Dictionary with parsed components or None if not a valid data line
        """
        # Pattern: IMPS_CODE NUMBER DESCRIPTION TRADES POUNDS LOW_PRICE - HIGH_PRICE WEIGHTED_AVG
        # Example: "109E 1 Rib, ribeye, lip-on, bn-in 55 119,191 1,266.00 - 1,616.00 1,359.01"

        # Use regex to match the pattern
        pattern = r'^(\S+)\s+(\d+)\s+(.+?)\s+(\d+)\s+([\d,]+)\s+([\d,.]+)\s*-\s*([\d,.]+)\s+([\d,.]+)\s*$'
        match = re.match(pattern, line.strip())

        if match:
            imps_code = match.group(1)
            # Skip the number (match.group(2)) as it's just a sequence number
            description = match.group(3).strip()
            trades = self._extract_number(match.group(4), is_integer=True)
            pounds = self._extract_number(match.group(5), is_integer=True)
            low_price = self._extract_number(match.group(6))
            high_price = self._extract_number(match.group(7))
            weighted_avg = self._extract_number(match.group(8))

            return {
                'imps_code': imps_code,
                'description': description,
                'trades': trades,
                'pounds': pounds,
                'low_price': low_price,
                'high_price': high_price,
                'weighted_avg': weighted_avg
            }

        return None

    def _parse_ground_beef_line(self, line: str) -> Optional[Dict]:
        """Parse a ground beef data line.

        Args:
            line: Text line to parse

        Returns:
            Dictionary with parsed components or None if not a valid data line
        """
        # Pattern: PRODUCT_NAME TRADES POUNDS LOW_PRICE - HIGH_PRICE WEIGHTED_AVG
        # Example: "Ground Beef 73%                         4      29,506    330.00 -  349.50        348.46"

        # Use regex to match the pattern - ground beef has no IMPS code
        pattern = r'^(.+?)\s+(\d+)\s+([\d,]+)\s+([\d,.]+)\s*-\s*([\d,.]+)\s+([\d,.]+)\s*$'
        match = re.match(pattern, line.strip())

        if match:
            product_name = match.group(1).strip()
            trades = self._extract_number(match.group(2), is_integer=True)
            pounds = self._extract_number(match.group(3), is_integer=True)
            low_price = self._extract_number(match.group(4))
            high_price = self._extract_number(match.group(5))
            weighted_avg = self._extract_number(match.group(6))

            return {
                'product_name': product_name,
                'trades': trades,
                'pounds': pounds,
                'low_price': low_price,
                'high_price': high_price,
                'weighted_avg': weighted_avg
            }

        return None

    def _clean_text(self, text: Optional[str]) -> str:
        """Clean and normalize text from PDF.

        Args:
            text: Raw text from PDF

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove special characters that might cause issues
        text = text.strip()

        return text

    def _extract_number(self, text: Optional[str], is_integer: bool = False) -> Optional[float]:
        """Extract a number from text.

        Args:
            text: Text containing a number
            is_integer: Whether to return as integer

        Returns:
            Extracted number or None
        """
        if not text:
            return None

        # Remove currency symbols, commas, and whitespace
        cleaned = re.sub(r'[$,\s]', '', str(text))

        # Extract number using regex
        match = re.search(r'-?\d+\.?\d*', cleaned)

        if match:
            try:
                number = float(match.group())
                return int(number) if is_integer else number
            except ValueError:
                return None

        return None

    def _is_header_row(self, text: str) -> bool:
        """Check if a row is likely a header or subtotal row.

        Args:
            text: Text to check

        Returns:
            True if likely a header row
        """
        header_indicators = [
            'total', 'subtotal', 'average', 'grand total',
            'report', 'date', 'page', 'continued', 'usda',
            'imps', 'fl', 'sub-primal', 'trades', 'pounds', 'price', 'range', 'weighted'
        ]

        text_lower = text.lower()
        return any(indicator in text_lower for indicator in header_indicators)

    def parse(self, report_type: str) -> List[Dict]:
        """Main parsing method to extract all pricing data.

        Args:
            report_type: Type of report being parsed

        Returns:
            List of pricing data dictionaries
        """
        logger.info(f"Starting to parse PDF: {self.pdf_path}")
        lines = self.extract_text_lines()
        pricing_data = self.parse_pricing_data(lines, report_type)
        logger.info(f"Parsing complete. Extracted {len(pricing_data)} records")
        return pricing_data


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    parser = PDFParser(pdf_path)
    data = parser.parse('branded_beef')

    print(f"\nExtracted {len(data)} pricing records:")
    for record in data[:5]:  # Show first 5 records
        print(f"\n{record['product_name']}")
        print(f"  Price: ${record['price']}")
        print(f"  Range: ${record['low_price']} - ${record['high_price']}")
        print(f"  Volume: {record['volume']} lbs")
        print(f"  Trades: {record['additional_data']['num_trades']}")
