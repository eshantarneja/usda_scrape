"""The pork report parser: block headers are the printed block names only (2026-11-03).

Before this, any short line without a price was taken for a block header, so an empty product row
("Butt Tender, FZN") became the block of the rows after it ("Butt Tender, FZN - - Backribs 2.0#/up"),
and the "AI (Added Ingreds)" block was never recognised, so enhanced items were stored under Variety.
"""
from pdf_parser import PDFParser

LINES = """
Pounds Price Range Wtd Avg
Loin
1/4 Trimmed Loin VAC 245,815 80.00 - 113.00 87.55
1/4 Trimmed Loin VAC, FZN -
Butt Tender -
Butt Tender, FZN -
Backribs 2.0#/up 38,058 225.56 - 270.00 241.87
Butt
1/4 Trim Butt VAC 828,414 83.00 - 139.07 101.96
Variety
Tails, Gas -
Tails, Combo 35,320 60.00 - 62.64 60.15
AI (Added Ingreds)
AI Bnls CC Strap On 40,077 108.00 - 190.00 112.03
AI Bnls CC Strap Off, FZN -
""".strip().splitlines()


def _parse():
    return PDFParser("unused.pdf").parse_pricing_data(LINES, 'pork_cuts')


def test_empty_rows_are_not_block_headers():
    names = [r['product_name'] for r in _parse()]
    assert 'Loin - Backribs 2.0#/up' in names
    assert not any(n.startswith('Butt Tender') for n in names)


def test_the_ai_block_is_a_block():
    rows = {r['product_name']: r for r in _parse()}
    assert 'AI - AI Bnls CC Strap On' in rows
    assert rows['AI - AI Bnls CC Strap On']['category'] == 'AI'
    assert rows['AI - AI Bnls CC Strap On']['additional_data']['sub_primal'] == 'AI Bnls CC Strap On'


def test_blocks_and_prices():
    rows = {r['product_name']: r for r in _parse()}
    assert rows['Loin - 1/4 Trimmed Loin VAC']['price'] == 87.55
    assert rows['Loin - 1/4 Trimmed Loin VAC']['volume'] == 245815
    assert rows['Butt - 1/4 Trim Butt VAC']['category'] == 'Butt'
    assert rows['Variety - Tails, Combo']['low_price'] == 60.0
    assert len(rows) == 5
