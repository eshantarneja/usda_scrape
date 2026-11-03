"""The two USDA lamb reports (2026-11-03): LM_XL500 domestic 5-day rolling average and LM_XL552 imported weekly.
Each prints a fresh block and a frozen block; a row with no trade ("0" or "-") is not a row."""
from pdf_parser import PDFParser

CUTS = """
FRESH CHOICE & PRIME CUTS
# of Total Weighted Change from
IMPS Sub-Primal Trades Pound Average Prior Days
200A Carcass, 3-way, 55/dn 0
204 Rack, 8-Rib, light 18 2,306 1,623.54 4.30
204C Rack, roast-ready, frenched 57 6,786 3,064.14 23.11
Breast, bulk
232 Loins, trimmed 1x1 40 3,339 1,142.42 -35.41
Necks 8 1,408 547.91 5.73
FROZEN CHOICE & PRIME CUTS
# of Total Weighted Change from
IMPS Sub-Primal Trades Pound Average Prior Days
204C Rack, roast-ready, frenched
210 Foreshank 15 3,650 785.17 8.44
296 Ground lamb 26 10,563 838.17 28.27
""".strip().splitlines()

IMPORTED = """
Negotiated Sales, Fresh
# of Total Weighted
Sub-Primal Trades Pounds Price Range Average
AUS Carcass, 35 lb/dn 0 -
AUS Rack, FR, Cap-off, 20-24 oz 7 5,225 1,595.00 - 1,732.00 1,619.52
AUS Shoulder, Square-cut 22 115,281 371.60 - 546.00 474.39
NZ Rack, FR, Cap-off, 12 oz/dn -
Negotiated Sales, Frozen
Sub-Primal Trades Pounds Price Range Average
AUS Leg, bnls 36 101,073 591.00 - 830.00 653.12
NZ Shortloin, 1-Rib, 0x0 33 143,637 591.60 - 874.00 784.29
""".strip().splitlines()


def test_domestic_rows_under_their_block():
    rows = {r['product_name']: r for r in PDFParser("unused.pdf").parse_pricing_data(CUTS, 'lamb_cuts')}
    assert set(rows) == {'Fresh - 204 Rack, 8-Rib, light', 'Fresh - 204C Rack, roast-ready, frenched', 'Fresh - 232 Loins, trimmed 1x1',
                         'Fresh - Necks', 'Frozen - 210 Foreshank', 'Frozen - 296 Ground lamb'}
    r = rows['Fresh - 204C Rack, roast-ready, frenched']
    assert r['price'] == 3064.14 and r['volume'] == 6786 and r['low_price'] is None and r['category'] == 'Fresh'
    assert r['additional_data'] == {'sub_primal': '204C Rack, roast-ready, frenched', 'trades': 57}
    assert rows['Fresh - 232 Loins, trimmed 1x1']['price'] == 1142.42          # a negative change column does not break the row
    assert rows['Frozen - 296 Ground lamb']['category'] == 'Frozen'


def test_imported_rows_keep_the_origin_prefix_and_the_range():
    rows = {r['product_name']: r for r in PDFParser("unused.pdf").parse_pricing_data(IMPORTED, 'lamb_imported')}
    assert set(rows) == {'Fresh - AUS Rack, FR, Cap-off, 20-24 oz', 'Fresh - AUS Shoulder, Square-cut',
                         'Frozen - AUS Leg, bnls', 'Frozen - NZ Shortloin, 1-Rib, 0x0'}
    r = rows['Fresh - AUS Rack, FR, Cap-off, 20-24 oz']
    assert (r['price'], r['low_price'], r['high_price'], r['volume']) == (1619.52, 1595.0, 1732.0, 5225)
    assert r['additional_data']['sub_primal'] == 'AUS Rack, FR, Cap-off, 20-24 oz'
    assert rows['Frozen - NZ Shortloin, 1-Rib, 0x0']['category'] == 'Frozen'


def test_nothing_before_the_first_block_is_a_row():
    assert PDFParser("unused.pdf").parse_pricing_data(["204 Rack, 8-Rib, light 18 2,306 1,623.54 4.30"], 'lamb_cuts') == []
