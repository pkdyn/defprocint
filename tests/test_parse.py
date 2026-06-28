"""Phase 1 gate: parse real defproc fixtures (captured live 2026-06-28).

Verifies the listing parser against the open Home latest-tenders feed and the
detail parser against a real per-tender page — schema, uniqueness, and a sample
diffed against what the live page actually showed.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.parse import (  # noqa: E402
    parse_listing, parse_detail, org_chain_clean,
    parse_indian_number, parse_gepnic_datetime, closing_display,
    parse_org_listing,
)

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def test_listing_schema_and_uniqueness():
    rows = parse_listing(_read("live_home.html"))
    assert len(rows) >= 5, f"expected real rows, got {len(rows)}"
    seen = set()
    for r in rows:
        assert r["title"], "empty title"
        assert r["closing_date"], "no closing date"
        assert r["closing_dt"] is not None, f"unparseable closing date: {r['title']}"
        assert r["detail_url"].startswith("http"), "detail_url not absolute"
        seen.add(r["detail_url"])
    assert len(seen) == len(rows), "detail_url not unique per row"


def test_listing_sample_matches_live_page():
    rows = parse_listing(_read("live_home.html"))
    # First live row on 2026-06-28: REPAIRS TO LEAKAGE/SEEPAGE..., ref 8969/E8.
    first = rows[0]
    assert first["title"].upper().startswith("REPAIRS TO LEAKAGE/SEEPAGE")
    assert first["ref_no"] == "8969/E8"
    assert first["closing_date"] == "18 Jul"


def test_detail_fields():
    d = parse_detail(_read("live_detail.html"))
    assert re.match(r"\d{4}_[A-Za-z0-9]+_\d+_\d+", d["tender_id"]), d["tender_id"]
    assert d["tender_id"] == "2026_MES_775135_1"
    assert "▸" in d["org_chain"] and "MILITARY ENGINEER SERVICES" in d["org_chain"].upper()
    assert d["value_inr"] == 1700000, d["value_inr"]
    assert d["tender_type"].lower().startswith("open")
    assert d["pincode"] == "786189", d["pincode"]
    assert "Garrison Engineer" in d["tia_name"], d["tia_name"]
    assert d["buyer_address"], "empty buyer address"
    assert "REPAIRS TO LEAKAGE" in d["description"].upper()


def test_helpers():
    assert org_chain_clean("A||B||C") == "A ▸ B ▸ C"
    assert parse_indian_number("17,00,000") == 1700000
    assert parse_indian_number("₹ 45,00,000.00") == 4500000
    assert parse_indian_number("NA") is None
    assert closing_display("18-Jul-2026 06:00 PM") == "18 Jul"
    dt = parse_gepnic_datetime("11-Jul-2026 06:00 PM")
    assert dt is not None and dt.hour == 18


def test_org_listing_parse():
    rows = parse_org_listing(_read("live_org_listing.html"))
    assert len(rows) >= 20, f"expected a full org tender list, got {len(rows)}"
    seen = set()
    for r in rows:
        assert r["title"], "empty title"
        assert r["detail_url"].startswith("http")
        assert r["org_chain"], "empty org_chain"
        seen.add(r["detail_url"])
    assert len(seen) == len(rows), "detail_url not unique"
    # at least some rows carry a parseable closing date + ref
    assert sum(1 for r in rows if r["closing_dt"] is not None) >= len(rows) // 2


def test_gated_detail_returns_empty():
    # The Active-Tenders CAPTCHA search page has no td_caption field table.
    d = parse_detail(_read("live_latest_active.html"))
    assert d == {}, "gated page should yield {} so caller degrades"


if __name__ == "__main__":
    for fn in [test_listing_schema_and_uniqueness, test_listing_sample_matches_live_page,
               test_detail_fields, test_helpers, test_gated_detail_returns_empty]:
        fn()
        print("ok:", fn.__name__)
    print("ALL PARSE TESTS PASSED")
