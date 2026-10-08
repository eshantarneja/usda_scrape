"""Parser fixture test for the USDA Prime report (LM_XB456 / AMS 2460).

Fixture: docs/2026-10-05-prime-report-sample.json — the USDA datamart's
"Prime Cuts" section for 2026-10-05 (report fields trimmed), the same week as
the PDF at /mnreports/ams_2460.pdf on 2026-10-08.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import prime_report  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "docs", "2026-10-05-prime-report-sample.json")


def _rows():
    with open(FIXTURE) as f:
        return prime_report.parse_rows(json.load(f)["results"])


def _find(rows, name):
    hits = [r for r in rows if r["product_name"] == name]
    assert len(hits) == 1, f"{name!r}: {len(hits)} hits"
    return hits[0]


def test_row_count_drops_blank_and_codeless_lines():
    rows = _rows()
    # 20 printed lines: 2 blank brackets (180 heavy, 184 heavy) and 1 codeless zero line dropped
    assert len(rows) == 17
    assert all(r["product_code"] for r in rows)
    assert all(r["price"] > 0 and r["volume"] > 0 and r["trades"] > 0 for r in rows)
    assert {r["category"] for r in rows} == {"Prime Cuts"}
    assert not any("heavy (180" in r["product_name"] for r in rows)


def test_door_row_shape():
    r = _find(_rows(), "180 - Loin, strip, bnls, 0x1")
    assert r["product_code"] == "180"
    assert r["price"] == 1547.44
    assert r["low_price"] == 1181.25 and r["high_price"] == 1698.5
    assert r["volume"] == 377181
    assert r["fat_limitation"] == 3 and r["trades"] == 184
    for key in ("category", "product_code", "product_name", "price", "low_price", "high_price", "volume"):
        assert key in r


def test_same_imps_kept_apart_by_description():
    rows = _rows()
    assert _find(rows, "112A - Rib, ribeye, bnls, light")["price"] == 1861.97
    assert _find(rows, "112A - Rib, ribeye, bnls, heavy")["price"] == 1766.56
    assert _find(rows, "174 - Loin, short loin, 2x3")["fat_limitation"] == 1
    assert _find(rows, "174 - Loin, short loin, 0x1")["fat_limitation"] == 3
    assert _find(rows, "175 - Loin, strip loin, 1x1")["price"] == 1333.8
    assert _find(rows, "109E - Rib, ribeye, lip-on, bn-in")["price"] == 1596.31
