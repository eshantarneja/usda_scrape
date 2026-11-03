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
        For cow_beef: Extracts the fresh cow cut sections (Boner/Breaker, Cutter/Canner, 100% Lean)
        For weekly_chicken / weekly_turkey: every priced line of the whole-bird and parts blocks

        Args:
            lines: List of text lines extracted from PDF
            report_type: Type of report being parsed

        Returns:
            List of dictionaries containing product pricing data
        """
        if report_type == 'daily_afternoon':
            return self._parse_daily_report(lines, report_type)
        elif report_type == 'pork_cuts':
            return self._parse_pork_report(lines, report_type)
        elif report_type in self.LAMB_BLOCKS:
            return self._parse_lamb_report(lines, report_type)
        elif report_type == 'cow_beef':
            return self._parse_cow_report(lines, report_type)
        elif report_type in self.POULTRY_TYPES:
            return self._parse_poultry_report(lines, report_type)
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
        # ORDER MATTERS: More specific matches must come first!
        section_markers = [
            ('Choice, Select & Ungraded', ('choice, select & ungraded', 'fat limitations')),
            ('Ground Beef', ('gb - steer/heifer source', '10 pound chub')),
            ('Choice Cuts', ('choice cuts', 'fat limitations')),
            ('Select Cuts', ('select cuts', 'fat limitations')),
        ]

        logger.info(f"Processing {len(lines)} lines for daily report")

        for line_idx, line in enumerate(lines):
            line_lower = line.lower().strip()

            # Check which section we're in
            section_found = False
            for section_name, keywords in section_markers:
                if all(kw in line_lower for kw in keywords):
                    current_section = section_name
                    logger.info(f"Found section at line {line_idx}: {section_name} | Line: {line[:80]}")
                    section_found = True
                    break

            # If we just found a section header, skip to next line
            if section_found:
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

                # Log first parse of each section with line details
                if current_section:
                    section_count = sum(1 for p in pricing_data if p['category'] == current_section)
                    if section_count == 0:
                        logger.info(f"First parse in {current_section} at line {line_idx}: {imps_code} | Trades: {trades}, Pounds: {pounds}, Avg: ${weighted_avg}")

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
                logger.debug(f"[{current_section}] Line {line_idx}: {product_name} - Avg: ${weighted_avg}, Range: ${low_price}-${high_price}, Volume: {pounds} lbs, Trades: {trades}")

        logger.info(f"Extracted {len(pricing_data)} pricing records from daily report")
        # Log counts by section
        from collections import Counter
        section_counts = Counter(p['category'] for p in pricing_data)
        for section, count in section_counts.items():
            logger.info(f"  {section}: {count} records")
        return pricing_data

    # ------------------------------------------------------------------ poultry
    # Weekly National Chicken (AMS 3646) and Turkey (AMS 3647) reports. Cents per lb.
    # A report is blocks ("Chicken, Whole - Cents Per Lb", "Chicken, Parts - ...") of
    # sections ("Domestic - Fresh - Conventional - FOB"); the chicken whole block also
    # has groups ("WOG Trading by Size:", "Whole Body Trading by Size:", "Regional and
    # Specific Destination Pricing:"). A line is: ITEM [Yes|No] LOW - HIGH WAVG and then,
    # each optional and in this order, CHANGE, 1,000-LBS, PREV-WAVG, PREV-1,000-LBS.
    # Long item names wrap onto the next line ("Breasts,Boneless/Skinless," / "Tom").
    POULTRY_TYPES = {'weekly_chicken': 'Chicken', 'weekly_turkey': 'Turkey'}
    POULTRY_BLOCK = re.compile(r'^(Chicken|Turkey),\s*(Whole|Parts?)\s*-\s*Cents Per Lb\s*$', re.I)
    # The third slot is the program: Conventional on most sections; the turkey report also prints
    # "Antibiotic Free" and "Organic" sections some weeks (seen in the 2025 archive).
    POULTRY_SECTION = re.compile(
        r'^(Domestic|Export)\s*-\s*(Fresh|Frozen)\s*-\s*(Conventional|Antibiotic Free|Organic|No Antibiotics Ever|NAE)\s*-\s*(Delivered|FOB)\s*$', re.I)
    POULTRY_GROUPS = {
        'wog trading by size:': 'WOG',
        'whole body trading by size:': 'Whole Body',
        'regional and specific destination pricing:': 'Regional',
    }
    POULTRY_LINE = re.compile(
        r'^(?P<item>.+?)\s+(?:(?P<offer>Yes|No)\s+)?'
        r'(?P<lo>\d[\d,]*\.\d+)\s*-\s*(?P<hi>\d[\d,]*\.\d+)\s+(?P<avg>\d[\d,]*\.\d+)'
        r'(?P<rest>(?:\s+-?[\d,]+(?:\.\d+)?)*)\s*$'
    )
    POULTRY_FURNITURE = ('weekly national', 'agricultural marketing', 'livestock, poultry', 'email us',
                         'report for:', 'current weeks trading', 'price range', 'offer price',
                         'usda ams', 'general inquiries', 'https://', 'www.')

    def _parse_poultry_report(self, lines: List[str], report_type: str) -> List[Dict]:
        """Parse a Weekly National Chicken / Turkey report (AMS 3646 / 3647).

        Every priced line is kept, export sections included (Demo's door decides
        what it wants). Prices stay in cents per lb as printed (unit 'cents/lb');
        volume is the printed thousands of pounds times 1,000. The product name
        carries the bird and the block or group ("Chicken WOG - 2.51 to 3.50 LB",
        "Chicken Parts - Breast - B/S", "Turkey Whole - Whole Young, Hen, Basted,
        8-16 lb, U.S. Grade A"); the category is the section line, normalised.
        """
        bird = self.POULTRY_TYPES[report_type]
        pricing_data: List[Dict] = []
        block = section = group = None
        last: Optional[Dict] = None   # the record a wrapped item name continues

        logger.info(f"Processing {len(lines)} lines for {report_type} report")

        for line_idx, line in enumerate(lines):
            s = ' '.join(line.split())
            if not s or s == '.':
                continue

            m = self.POULTRY_BLOCK.match(s)
            if m:
                block = 'Parts' if m.group(2).lower().startswith('part') else 'Whole'
                group, last = None, None
                logger.info(f"Found poultry block at line {line_idx}: {bird} {block}")
                continue
            m = self.POULTRY_SECTION.match(s)
            if m:
                market, state, program = m.group(1).title(), m.group(2).title(), m.group(3).title()
                program = 'NAE' if program.lower() == 'nae' else program
                basis = 'FOB' if m.group(4).lower() == 'fob' else 'Delivered'
                section = f"{market} - {state} - {program} - {basis}"
                last = None
                logger.info(f"Found poultry section at line {line_idx}: {section}")
                continue
            g = self.POULTRY_GROUPS.get(s.lower())
            if g:
                group, last = g, None
                continue
            if any(k in s.lower() for k in self.POULTRY_FURNITURE):
                last = None
                continue

            m = self.POULTRY_LINE.match(s)
            if m and block and section:
                item = m.group('item').strip().rstrip(':').strip()
                tail = self._poultry_tail(m.group('rest'))
                volume = tail['volume']
                record = {
                    'product_name': self._poultry_name(bird, block, group, item),
                    'product_code': None,
                    'price': self._extract_number(m.group('avg')),
                    'low_price': self._extract_number(m.group('lo')),
                    'high_price': self._extract_number(m.group('hi')),
                    'volume': volume * 1000 if volume is not None else None,
                    'unit': 'cents/lb',
                    'report_type': report_type,
                    'category': section,
                    'additional_data': {
                        'bird': bird,
                        'block': block,
                        'group': group,
                        'item': item,
                        'market': section.split(' - ')[0],
                        'state': section.split(' - ')[1],
                        'program': section.split(' - ')[2],
                        'basis': section.split(' - ')[3],
                        'offer': m.group('offer'),
                        'change': tail['change'],
                        'prev_price': tail['prev_price'],
                        'prev_volume': tail['prev_volume'] * 1000 if tail['prev_volume'] is not None else None,
                    },
                }
                if record['price']:
                    pricing_data.append(record)
                    last = record
                else:
                    last = None
                continue

            # A bare text line right after a priced line is the rest of its item name
            # ("National Composite Whole" + "Bird:", "Mechanically Separated, 15-" + "20% Fat Content").
            if last is not None and not re.search(r'\d[\d,]*\.\d+\s*-\s*\d', s):
                item = last['additional_data']['item']
                cont = s.strip().rstrip(':').strip()
                item = item + cont if item.endswith('-') else f"{item} {cont}"
                last['additional_data']['item'] = item
                last['product_name'] = self._poultry_name(bird, block, last['additional_data']['group'], item)
                continue
            last = None

        logger.info(f"Extracted {len(pricing_data)} pricing records from {report_type} report")
        from collections import Counter
        for sec, count in Counter(p['category'] for p in pricing_data).items():
            logger.info(f"  {sec}: {count} records")
        return pricing_data

    @staticmethod
    def _poultry_name(bird: str, block: str, group: Optional[str], item: str) -> str:
        label = group if (block == 'Whole' and group) else block
        return f"{bird} {label} - {item}"

    def _poultry_tail(self, rest: Optional[str]) -> Dict:
        """CHANGE, 1,000-LBS, PREV-WAVG, PREV-1,000-LBS, each optional, told apart by shape:
        a price has a decimal point, a volume never does."""
        out = {'change': None, 'volume': None, 'prev_price': None, 'prev_volume': None}
        for tok in (rest or '').split():
            if '.' in tok:
                key = 'change' if (out['change'] is None and out['volume'] is None) else 'prev_price'
            else:
                key = 'volume' if out['volume'] is None else 'prev_volume'
            if out[key] is None:
                out[key] = self._extract_number(tok, is_integer=('.' not in tok))
        return out

    # Cow report (LM_XB461 / ams_2463) line shape: IMPS DESC TRADES POUNDS WAVG [CHANGE]
    # No fat-limitation digit, no low-high range; the prior-week change is optional
    # and prints negatives in parentheses. IMPS code is optional (100% Lean items,
    # "Chuck, boneless 85%", "Flank, rough" carry none).
    COW_LINE = re.compile(
        r'^(?:(\d{3}[A-Z]?)\s+)?(.+?)\s+(\d+)\s+([\d,]+)\s+([\d,.]+)(?:\s+\(?-?[\d,.]+\)?)?\s*$'
    )
    # Section markers are bare ALL-CAPS lines. Longer names first so that
    # "FROZEN BONER/BREAKER & CUTTER/CANNER" is not read as "BONER/BREAKER".
    COW_SECTIONS = [
        ('FROZEN BONER/BREAKER & CUTTER/CANNER', False),
        ('FROZEN CUTTER/CANNER', False),
        ('FROZEN BONER/BREAKER', False),
        ('BONER/BREAKER & CUTTER/CANNER', True),
        ('100% LEAN', True),
        ('CUTTER/CANNER', True),
        ('BONER/BREAKER', True),
    ]

    COW_FURNITURE = ('usda', 'page ', 'mymarketnews', 'www.', 'agricultural marketing',
                     'livestock, poultry', 'imps sub-primal', 'change from')

    def _parse_cow_report(self, lines: List[str], report_type: str) -> List[Dict]:
        """Parse the weekly cutter cow report (LM_XB461).

        Page 1 is a cutout-value table with the same numeric shape as a cut
        line, so nothing is parsed until the first section marker. The three
        FROZEN sections repeat the fresh IMPS codes and are skipped. Rows with
        zero trades, or with no numbers at all, are dropped. The section name
        is stored as the category; there is no low/high range in this report.
        """
        pricing_data = []
        current_section = None   # None until the first marker; False inside a skipped section
        skip_section = True

        logger.info(f"Processing {len(lines)} lines for cow report")

        for line_idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            marker = next((name for name, _ in self.COW_SECTIONS if stripped.upper() == name), None)
            if marker is not None:
                current_section = marker
                skip_section = not dict(self.COW_SECTIONS)[marker]
                logger.info(f"Found cow section at line {line_idx}: {marker}{' (skipped)' if skip_section else ''}")
                continue

            if current_section is None or skip_section:
                continue
            # Not the shared _is_header_row: its 'fl' indicator would eat
            # "Flank", "Flats and eyes" and "butt flap". Page furniture only.
            if any(k in stripped.lower() for k in self.COW_FURNITURE):
                continue

            match = self.COW_LINE.match(stripped)
            if not match:
                continue

            imps_code = match.group(1)
            description = match.group(2).strip()
            trades = self._extract_number(match.group(3), is_integer=True)
            pounds = self._extract_number(match.group(4), is_integer=True)
            weighted_avg = self._extract_number(match.group(5))

            if not trades or not pounds or not weighted_avg:
                continue

            product_name = f"{imps_code} - {description}" if imps_code else description
            pricing_data.append({
                'product_name': product_name,
                'product_code': imps_code,
                'price': weighted_avg,
                'low_price': None,
                'high_price': None,
                'volume': pounds,
                'report_type': report_type,
                'category': current_section,
                'additional_data': {
                    'num_trades': trades,
                    'imps_code': imps_code,
                    'sub_primal': description
                }
            })
            logger.debug(f"[{current_section}] Line {line_idx}: {product_name} - Avg: ${weighted_avg}, Volume: {pounds} lbs, Trades: {trades}")

        logger.info(f"Extracted {len(pricing_data)} pricing records from cow report")
        from collections import Counter
        for section, count in Counter(p['category'] for p in pricing_data).items():
            logger.info(f"  {section}: {count} records")
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

    def _parse_pork_report(self, lines: List[str], report_type: str) -> List[Dict]:
        """Parse pork report with category headers and product lines.

        Pork reports have a different format than beef:
        - No IMPS codes
        - Category headers (e.g., "Loin", "Butt") followed by product lines
        - Format: ProductName Pounds Low-High Avg
        """
        pricing_data = []
        current_category = None
        in_data_section = False

        logger.info(f"Processing {len(lines)} lines for pork report")

        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                continue

            # Check if this is the start of data section (after header info)
            # Look for "Pounds" and "Price Range" to identify we're in the data area
            # This must come BEFORE _is_header_row check since column headers contain those keywords
            if 'pounds' in line_stripped.lower() and 'price' in line_stripped.lower():
                in_data_section = True
                logger.info(f"Found data section header at line {line_idx}: {line_stripped}")
                continue

            if not in_data_section:
                continue

            # Skip header rows (only after we're in data section)
            if self._is_header_row(line_stripped):
                continue

            # Try to parse as a product line first
            parsed = self._parse_pork_line(line_stripped)

            if parsed:
                # This is a product line with price data
                product_name = parsed['product_name']

                # Build full product name with category prefix
                if current_category:
                    full_product_name = f"{current_category} - {product_name}"
                else:
                    full_product_name = product_name

                pricing_record = {
                    'product_name': full_product_name,
                    'product_code': None,  # Pork has no IMPS codes
                    'price': parsed['weighted_avg'],
                    'low_price': parsed['low_price'],
                    'high_price': parsed['high_price'],
                    'volume': parsed['pounds'],
                    'report_type': report_type,
                    'category': current_category,
                    'meat_type': 'pork',
                    'additional_data': {
                        'sub_primal': product_name
                    }
                }

                pricing_data.append(pricing_record)
                logger.debug(f"[{current_category}] Parsed: {full_product_name} - Avg: ${parsed['weighted_avg']}, Volume: {parsed['pounds']} lbs")
            else:
                # This might be a category header (line without price data)
                # Category headers are typically short text without numbers
                if self._is_pork_category_header(line_stripped):
                    current_category = self.PORK_BLOCKS[line_stripped.lower().strip()]
                    logger.info(f"Found category header at line {line_idx}: {current_category}")

        logger.info(f"Extracted {len(pricing_data)} pricing records from pork report")

        # Log counts by category
        from collections import Counter
        category_counts = Counter(p['category'] for p in pricing_data if p['category'])
        for category, count in category_counts.items():
            logger.info(f"  {category}: {count} records")

        return pricing_data


    # The two USDA lamb reports (2026-11-03, Demo 449). Each prints a fresh block and a frozen block;
    # the block header is the only thing that says which. Rows with no trade print "0" or "-" and
    # are not rows. LM_XL500 (lamb_cuts) rows: "<IMPS> <item> <trades> <pounds> <wtd avg> <change>";
    # LM_XL552 (lamb_imported) rows: "<AUS|NZ> <item> <trades> <pounds> <low> - <high> <wtd avg>".
    LAMB_BLOCKS = {
        'lamb_cuts': {'fresh choice & prime cuts': 'Fresh', 'frozen choice & prime cuts': 'Frozen'},
        'lamb_imported': {'negotiated sales, fresh': 'Fresh', 'negotiated sales, frozen': 'Frozen'},
    }
    _LAMB_CUTS_ROW = re.compile(r'^(.+?)\s+(\d+)\s+([\d,]+)\s+([\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s*$')
    _LAMB_IMPORTED_ROW = re.compile(r'^(.+?)\s+(\d+)\s+([\d,]+)\s+([\d,]+\.\d{2})\s*-\s*([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$')

    def _parse_lamb_report(self, lines: List[str], report_type: str) -> List[Dict]:
        """Parse LM_XL500 (lamb_cuts) or LM_XL552 (lamb_imported): every priced row under its
        fresh / frozen block, the item text kept whole in additional_data.sub_primal."""
        blocks = self.LAMB_BLOCKS[report_type]
        row_re = self._LAMB_CUTS_ROW if report_type == 'lamb_cuts' else self._LAMB_IMPORTED_ROW
        pricing_data: List[Dict] = []
        block = None
        for line in lines:
            t = line.strip()
            if not t:
                continue
            key = t.lower()
            if key in blocks:
                block = blocks[key]
                continue
            if block is None:
                continue
            m = row_re.match(t)
            if not m:
                continue
            name = m.group(1).strip()
            if report_type == 'lamb_cuts':
                trades = self._extract_number(m.group(2), is_integer=True)
                pounds = self._extract_number(m.group(3), is_integer=True)
                avg = self._extract_number(m.group(4))
                low = high = None
            else:
                trades = self._extract_number(m.group(2), is_integer=True)
                pounds = self._extract_number(m.group(3), is_integer=True)
                low = self._extract_number(m.group(4))
                high = self._extract_number(m.group(5))
                avg = self._extract_number(m.group(6))
            if not avg or not pounds:
                continue
            pricing_data.append({
                'product_name': f"{block} - {name}",
                'product_code': None,
                'price': avg,
                'low_price': low,
                'high_price': high,
                'volume': pounds,
                'report_type': report_type,
                'category': block,
                'meat_type': 'lamb',
                'additional_data': {'sub_primal': name, 'trades': trades},
            })
        logger.info(f"Extracted {len(pricing_data)} pricing records from {report_type}")
        return pricing_data

    def _parse_pork_line(self, line: str) -> Optional[Dict]:
        """Parse a pork product data line.

        Args:
            line: Text line to parse

        Returns:
            Dictionary with parsed components or None if not a valid data line
        """
        # Pattern: ProductName Pounds Low - High Avg
        # Example: "1/4 Trimmed Loin VAC    171,141    92.50 - 109.90    97.72"

        pattern = r'^(.+?)\s+([\d,]+)\s+([\d,.]+)\s*-\s*([\d,.]+)\s+([\d,.]+)\s*$'
        match = re.match(pattern, line.strip())

        if match:
            product_name = match.group(1).strip()
            pounds = self._extract_number(match.group(2), is_integer=True)
            low_price = self._extract_number(match.group(3))
            high_price = self._extract_number(match.group(4))
            weighted_avg = self._extract_number(match.group(5))

            # Validate that we have reasonable values
            if pounds and low_price and high_price and weighted_avg:
                return {
                    'product_name': product_name,
                    'pounds': pounds,
                    'low_price': low_price,
                    'high_price': high_price,
                    'weighted_avg': weighted_avg
                }

        return None

    # The block headers LM_PK602 prints, and nothing else (2026-11-03). The old guess ("a short line
    # with no numbers") turned every empty product row ("Butt Tender, FZN", "Tails, Gas") into a block,
    # so the next real row was stored as "Butt Tender, FZN - - Backribs 2.0#/up", and the AI block
    # (printed "AI (Added Ingreds)") was never a header, so its rows landed under "Variety".
    PORK_BLOCKS = {
        'loin': 'Loin', 'butt': 'Butt', 'picnic': 'Picnic', 'sparerib': 'Sparerib', 'ham': 'Ham',
        'belly': 'Belly', 'jowl': 'Jowl', 'trim': 'Trim', 'variety': 'Variety',
        'ai (added ingreds)': 'AI', 'ai (added ingredients)': 'AI', 'ai': 'AI',
    }

    def _is_pork_category_header(self, line: str) -> bool:
        """A pork block header is one of the printed block names, exactly; anything else is a product row
        (with or without a price)."""
        return line.lower().strip() in self.PORK_BLOCKS

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
