"""Parser fixture tests for the USDA Weekly National Chicken (AMS 3646) and
Turkey (AMS 3647) reports.

Fixtures: docs/2026-10-30-chicken-report-sample.txt and
docs/2026-10-30-turkey-report-sample.txt (pdfplumber text of the 2026-10-30
reports, "===== PAGE N =====" separators added). Expected values read off the
PDFs by hand on 2026-11-02.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pdf_parser import PDFParser  # noqa: E402

DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")


def _lines(name):
    with open(os.path.join(DOCS, name)) as f:
        return [ln.rstrip("\n") for ln in f if not ln.startswith("===== PAGE")]


def _chicken():
    return PDFParser("unused.pdf").parse_pricing_data(_lines("2026-10-30-chicken-report-sample.txt"), "weekly_chicken")


def _turkey():
    return PDFParser("unused.pdf").parse_pricing_data(_lines("2026-10-30-turkey-report-sample.txt"), "weekly_turkey")


def _find(rows, name, category=None):
    hits = [r for r in rows if r["product_name"] == name and (category is None or r["category"] == category)]
    assert len(hits) == 1, f"{name!r} in {category!r}: {len(hits)} hits ({[r['product_name'] for r in rows]})"
    return hits[0]


# ----------------------------------------------------------------- chicken

def test_chicken_row_counts():
    rows = _chicken()
    assert len(rows) == 33          # 17 whole-bird rows + 15 domestic parts + 1 export MSC
    assert all(r["product_code"] is None for r in rows)
    assert all(r["unit"] == "cents/lb" for r in rows)
    assert all(r["report_type"] == "weekly_chicken" for r in rows)
    assert all(r["price"] > 0 for r in rows)
    cats = {r["category"] for r in rows}
    assert cats == {"Domestic - Fresh - Conventional - Delivered",
                    "Domestic - Fresh - Conventional - FOB",
                    "Export - Frozen - Conventional - FOB"}


def test_chicken_wog_by_size():
    rows = _chicken()
    r = _find(rows, "Chicken WOG - 2.51 to 3.50 LB")
    assert r["category"] == "Domestic - Fresh - Conventional - Delivered"
    assert r["low_price"] == 80.0 and r["high_price"] == 145.0 and r["price"] == 117.64
    assert r["volume"] == 3_556_000          # printed 3,556 thousand lbs
    a = r["additional_data"]
    assert a["block"] == "Whole" and a["group"] == "WOG" and a["item"] == "2.51 to 3.50 LB"
    assert a["state"] == "Fresh" and a["basis"] == "Delivered" and a["market"] == "Domestic"
    assert a["change"] == 0.40 and a["prev_price"] == 117.24 and a["prev_volume"] == 3_479_000
    assert _find(rows, "Chicken WOG - 2.50 LB and lighter")["price"] == 132.54
    assert _find(rows, "Chicken WOG - 3.51 LB and heavier")["price"] == 90.50
    assert _find(rows, "Chicken WOG - National Composite WOGS")["price"] == 116.28


def test_chicken_whole_body_and_composite_wrap():
    rows = _chicken()
    # "National Composite Whole" + "Bird:" on the next line
    r = _find(rows, "Chicken Whole - National Composite Whole Bird")
    assert r["price"] == 117.37 and r["volume"] == 6_934_000
    assert r["additional_data"]["change"] == -0.02
    assert _find(rows, "Chicken Whole Body - National Composite")["price"] == 129.38
    assert _find(rows, "Chicken Whole Body - 3.01 LB and heavier")["price"] == 128.03
    assert _find(rows, "Chicken Regional - Eastern WOGS")["price"] == 113.60
    assert _find(rows, "Chicken Regional - Chicago Whole Body")["additional_data"]["change"] == -0.33
    assert len([r for r in rows if r["additional_data"]["group"] == "Regional"]) == 9


def test_chicken_parts():
    rows = _chicken()
    r = _find(rows, "Chicken Parts - Breast - B/S", "Domestic - Fresh - Conventional - FOB")
    assert r["price"] == 111.80 and r["low_price"] == 99.0 and r["high_price"] == 137.0
    assert r["volume"] == 1_239_000 and r["additional_data"]["change"] == -1.20
    assert _find(rows, "Chicken Parts - Thighs - B/S")["price"] == 170.46
    assert _find(rows, "Chicken Parts - Thighs - Bone-in")["volume"] == 6_000
    assert _find(rows, "Chicken Parts - Wings - Whole")["price"] == 107.10
    assert _find(rows, "Chicken Parts - Leg quarters - Bulk")["price"] == 53.72
    assert _find(rows, "Chicken Parts - Legs - Bone-in")["price"] == 74.58
    assert _find(rows, "Chicken Parts - Tenderloins")["price"] == 114.04
    assert _find(rows, "Chicken Parts - Gizzards and Hearts")["price"] == 90.09
    assert _find(rows, "Chicken Parts - Backs and Necks Stripped")["price"] == 10.60
    # the same item in two sections stays two rows
    assert _find(rows, "Chicken Parts - MSC, 15-20% Fat Content", "Domestic - Fresh - Conventional - FOB")["price"] == 23.14
    assert _find(rows, "Chicken Parts - MSC, 15-20% Fat Content", "Export - Frozen - Conventional - FOB")["price"] == 25.69


def test_chicken_no_furniture_rows():
    names = [r["product_name"] for r in _chicken()]
    assert not any("Price Range" in n or "Trading" in n or "USDA" in n for n in names)


# ------------------------------------------------------------------ turkey

def test_turkey_row_counts():
    rows = _turkey()
    assert len(rows) == 17          # 2 whole + 4 fresh parts + 6 frozen parts + 2 export fresh + 3 export frozen
    cats = {r["category"] for r in rows}
    assert cats == {"Domestic - Frozen - Conventional - FOB",
                    "Domestic - Fresh - Conventional - Delivered",
                    "Domestic - Frozen - Conventional - Delivered",
                    "Export - Fresh - Conventional - Delivered",
                    "Export - Frozen - Conventional - Delivered"}
    assert all(r["report_type"] == "weekly_turkey" for r in rows)


def test_turkey_whole_offer_rows_wrap_and_have_no_volume():
    rows = _turkey()
    r = _find(rows, "Turkey Whole - Whole Young, Hen, Basted, 8-16 lb, U.S. Grade A")
    assert r["category"] == "Domestic - Frozen - Conventional - FOB"
    assert r["low_price"] == 177.0 and r["high_price"] == 197.0 and r["price"] == 187.0
    assert r["volume"] is None and r["additional_data"]["offer"] == "Yes"
    assert _find(rows, "Turkey Whole - Whole Young, Tom, Basted, 16-24 lb, U.S. Grade A")["price"] == 188.5


def test_turkey_parts_wraps_and_tail_columns():
    rows = _turkey()
    r = _find(rows, "Turkey Parts - Breasts,Boneless/Skinless, Tom", "Domestic - Fresh - Conventional - Delivered")
    assert r["price"] == 289.60 and r["volume"] == 200_000
    assert r["additional_data"]["change"] == 4.96 and r["additional_data"]["prev_price"] == 284.64
    assert r["additional_data"]["prev_volume"] == 440_000 and r["additional_data"]["offer"] == "No"
    # "Mechanically Separated, 15-" + "20% Fat Content" joins without a space after the hyphen
    r = _find(rows, "Turkey Parts - Mechanically Separated, 15-20% Fat Content", "Domestic - Fresh - Conventional - Delivered")
    assert r["price"] == 22.33
    r = _find(rows, "Turkey Parts - Thigh Meat,Boneless Skinless")
    assert r["price"] == 121.0 and r["additional_data"]["change"] == -0.67
    # the same item in fresh and frozen sections stays two rows
    assert _find(rows, "Turkey Parts - Drumsticks, Tom", "Domestic - Fresh - Conventional - Delivered")["price"] == 96.5
    assert _find(rows, "Turkey Parts - Drumsticks, Tom", "Domestic - Frozen - Conventional - Delivered")["price"] == 100.81


def test_turkey_program_sections_are_sections_not_item_text():
    # Some 2025 weeks print "Antibiotic Free" / "Organic" sections; before the fix the header was glued
    # onto the previous item ("Wings,Full-Cut, Tom Domestic - Frozen - Antibiotic Free - Delivered").
    lines = ["Turkey, Part - Cents Per Lb",
             "Domestic - Frozen - Conventional - Delivered",
             "Offer Price Range Wtd Avg Change 1,000 lbs Wtd Avg 1,000 lbs",
             "Wings,Full-Cut, Tom No 142.00 - 142.00 142.00 10.71 14 131.29 560",
             "Domestic - Frozen - Antibiotic Free - Delivered",
             "Offer Price Range Wtd Avg Change 1,000 lbs Wtd Avg 1,000 lbs",
             "Wings,Full-Cut, Tom No 150.00 - 150.00 150.00 10",
             "Domestic - Fresh - Organic - Delivered",
             "Breasts,Boneless/Skinless, No 320.00 - 320.00 320.00 20",
             "Tom"]
    rows = PDFParser("unused.pdf").parse_pricing_data(lines, "weekly_turkey")
    assert [r["product_name"] for r in rows] == ["Turkey Parts - Wings,Full-Cut, Tom",
                                                 "Turkey Parts - Wings,Full-Cut, Tom",
                                                 "Turkey Parts - Breasts,Boneless/Skinless, Tom"]
    assert [r["category"] for r in rows] == ["Domestic - Frozen - Conventional - Delivered",
                                             "Domestic - Frozen - Antibiotic Free - Delivered",
                                             "Domestic - Fresh - Organic - Delivered"]
    assert rows[1]["volume"] == 10_000 and rows[1]["additional_data"]["program"] == "Antibiotic Free"
    assert rows[2]["additional_data"]["program"] == "Organic"


def test_turkey_volume_only_tail_is_volume_not_change():
    rows = _turkey()
    r = _find(rows, "Turkey Parts - Wing Meat with Skin")
    assert r["price"] == 60.0 and r["volume"] == 120_000
    assert r["additional_data"]["change"] is None and r["additional_data"]["prev_price"] is None
    # page 2 opens with a row that continues page 1's frozen section
    r = _find(rows, "Turkey Parts - Wings,V-Type, Tom")
    assert r["category"] == "Domestic - Frozen - Conventional - Delivered"
    assert r["price"] == 193.0 and r["volume"] == 40_000
    assert _find(rows, "Turkey Parts - Gizzards,Defatted")["category"] == "Export - Frozen - Conventional - Delivered"
    assert _find(rows, "Turkey Parts - Tails", "Export - Frozen - Conventional - Delivered")["price"] == 80.5
