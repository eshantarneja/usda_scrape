"""Parser fixture test for the USDA cow report (LM_XB461 / ams_2463).

Fixture: docs/2026-09-04-cow-report-sample.txt (pdfplumber text of the
2026-09-04 report, with "===== PAGE N =====" separators added by hand).
Expected rows come from docs/2026-09-04-cow-report-findings.md.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pdf_parser import PDFParser  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "docs", "2026-09-04-cow-report-sample.txt")


def _lines():
    with open(FIXTURE) as f:
        return [ln.rstrip("\n") for ln in f if not ln.startswith("===== PAGE")]


def _rows():
    return PDFParser("unused.pdf").parse_pricing_data(_lines(), "cow_beef")


def _find(rows, name, category=None):
    hits = [r for r in rows if r["product_name"] == name and (category is None or r["category"] == category)]
    assert len(hits) == 1, f"{name!r} in {category!r}: {len(hits)} hits"
    return hits[0]


def test_row_counts():
    rows = _rows()
    assert len(rows) == 27
    assert sum(1 for r in rows if r["product_code"]) == 19
    assert sum(1 for r in rows if not r["product_code"]) == 8  # 6 x 100% Lean + Chuck boneless 85% + Flank rough


def test_sections_and_no_frozen_or_cutout_rows():
    rows = _rows()
    cats = {r["category"] for r in rows}
    assert cats == {"BONER/BREAKER", "CUTTER/CANNER", "100% LEAN", "BONER/BREAKER & CUTTER/CANNER"}
    assert all(r["price"] > 0 for r in rows)
    assert all(r["volume"] > 0 for r in rows)
    assert all(r["additional_data"]["num_trades"] > 0 for r in rows)
    assert all(r["report_type"] == "cow_beef" for r in rows)
    # page-1 cutout table must not leak in
    assert not any(r["product_name"].startswith("90% lean") for r in rows)
    assert not any("Kidney" in r["product_name"] for r in rows)


def test_coded_line_with_negative_change():
    r = _find(_rows(), "112 - Rib, ribeye roll, 8-10 lbs.", "BONER/BREAKER")
    assert r["product_code"] == "112"
    assert r["price"] == 710.18
    assert r["volume"] == 56119
    assert r["additional_data"]["num_trades"] == 26
    assert r["low_price"] is None and r["high_price"] is None
    assert r["additional_data"]["imps_code"] == "112"
    assert r["additional_data"]["sub_primal"] == "Rib, ribeye roll, 8-10 lbs."


def test_coded_line_without_change_column():
    r = _find(_rows(), "168 - Round, top inside, 10-dn lbs.", "BONER/BREAKER")
    assert r["price"] == 376.16 and r["volume"] == 32904
    assert r["additional_data"]["num_trades"] == 5


def test_same_imps_code_by_bracket_and_section():
    rows = _rows()
    # 112 appears in two fresh sections; brackets keep the rows distinct
    assert _find(rows, "112 - Rib, ribeye roll, 6-8 lbs.", "CUTTER/CANNER")["price"] == 704.73
    assert _find(rows, "112 - Rib, ribeye roll, 8-up lbs.", "CUTTER/CANNER")["price"] == 697.58
    assert _find(rows, "112 - Rib, ribeye roll, 10-up lbs.", "BONER/BREAKER")["price"] == 698.26
    assert len([r for r in rows if r["product_code"] == "190"]) == 4


def test_codeless_lines():
    rows = _rows()
    r = _find(rows, "Flank, rough", "BONER/BREAKER & CUTTER/CANNER")
    assert r["product_code"] is None and r["price"] == 508.79
    r = _find(rows, "Chuck, boneless 85%", "BONER/BREAKER")
    assert r["product_code"] is None and r["price"] == 442.31
    lean = [r for r in rows if r["category"] == "100% LEAN"]
    assert len(lean) == 6
    assert all(r["product_code"] is None for r in lean)
    assert _find(rows, "Striploin", "100% LEAN")["price"] == 643.88
