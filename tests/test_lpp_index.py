"""Phase gate: LPP archive index builds & loads; DPM 2025 mapping is correct;
the dashboard is wired to the index and carries the DPMF 5/7 export."""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.index_lpp import (  # noqa: E402
    build_index, to_lpp_record, lpp_fy, lpp_vintage, soc_export_block, LPP_FIELDS,
)

NOW = datetime(2026, 6, 28, tzinfo=timezone.utc)
DASH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "web", "defproc-tender-watch.html")

# Two sample corpus records: one current (value not published), one AoC-awarded.
CORPUS = [
    {"tender_id": "2026_MES_775135_1", "title": "REPAIRS TO LEAKAGE/SEEPAGE plumbing",
     "org_chain": "MES ▸ CE Shillong Zone", "unit": "Garrison Engineer Dinjan No 02",
     "location": "Tinsukia", "tender_type": "Open Tender", "closing_iso": "2026-07-18",
     "criticality": "routine", "domains": [], "named_system": None, "value_inr": 1700000,
     "detail_url": "https://defproc.gov.in/x", "category": "Civil Works"},
    {"tender_id": "2021_IN_ENC_14002_1", "title": "SIGINT receiver and EW pod calibration",
     "org_chain": "MoD ▸ Indian Navy ▸ ENC", "unit": "HQ Eastern Naval Command",
     "location": "Visakhapatnam", "tender_type": "Single Tender", "closing_iso": "2021-10-11",
     "criticality": "critical", "domains": ["EW_SIGINT"], "named_system": None,
     "awarded_value": 9600000, "l1": "BEL", "detail_url": "https://defproc.gov.in/y"},
]


def test_index_builds_and_loads():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "lpp-index.json")
        doc = build_index(CORPUS, out_path=out, now=NOW)
        on_disk = json.load(open(out, encoding="utf-8"))
    assert on_disk["count"] == 2 == len(on_disk["records"])
    assert on_disk["built"].endswith("Z")
    # sorted newest-first
    assert on_disk["records"][0]["id"] == "2026_MES_775135_1"


def test_records_carry_5351_fields():
    rec = to_lpp_record(CORPUS[0])
    for f in ("id", "title", "unit", "mode", "date", "qty", "value", "l1",
              "detail_url", "source", "category"):
        assert f in rec
    assert rec["mode"] == "Open Tender"           # §5.35.1 mode of tendering
    assert rec["detail_url"].startswith("http")
    assert rec["value"] is None                   # not published -> obtain from unit
    assert rec["est_value"] == 1700000            # estimated tender value kept separately


def test_awarded_value_captured_where_published():
    rec = to_lpp_record(CORPUS[1])
    assert rec["value"] == 9600000 and rec["l1"] == "BEL"


def test_est_value_never_becomes_lpp():
    # An active tender with only an ESTIMATE must show no LPP value (estimate is
    # not a last-purchase price). The estimate is kept separately as est_value.
    rec = to_lpp_record({"tender_id": "A", "title": "x", "criticality": "routine",
                         "value_inr": 5000000, "closing_iso": "2026-07-01"})  # no awarded_value
    assert rec["value"] is None, "estimate must NOT be exposed as LPP value"
    assert rec["est_value"] == 5000000
    # the DPM export likewise refuses to print a price for it
    block = soc_export_block(rec, NOW)
    assert "to be obtained from the buying unit" in block
    assert "50.00 lakh" not in block  # the estimate is never rendered as the LPP

    # whole-index invariant: no record exposes its estimate as the LPP value
    doc = build_index([{"tender_id": "A", "title": "x", "criticality": "routine",
                        "value_inr": 5000000}], out_path="", now=NOW)
    for r in doc["records"]:
        assert r["value"] is None or r["value"] != r["est_value"]


def test_vintage_and_fy():
    assert lpp_fy("2021-10-11") == "2021-22"
    assert lpp_fy("2026-07-18") == "2026-27"
    assert lpp_vintage("2026-07-18", NOW) == 0
    assert lpp_vintage("2021-10-11", NOW) == 5   # > 3 FY -> §5.33.4(a) flag


def test_export_block_is_valid_dpm():
    rec = to_lpp_record(CORPUS[1])
    txt = soc_export_block(rec, NOW)
    assert "DPMF 5 — Statement of Case, Ser 7" in txt
    assert "DPMF 5 Ser 6(a) / DPMF 7" in txt
    assert "§5.33.4" in txt
    assert "§5.32.2" in txt                       # escalation/ERV left to indenter
    assert "Escalation factor: __________" in txt
    assert "EXCEEDS 3 yrs" in txt                 # vintage 5 FY flagged
    assert "₹96.00 lakh" in txt                   # awarded value rendered
    # Not-published case shows the obtain-from-unit text, no fabricated price.
    txt0 = soc_export_block(to_lpp_record(CORPUS[0]), NOW)
    assert "to be obtained from the buying unit" in txt0


def test_dashboard_wired_to_index_and_has_export():
    html = open(DASH, encoding="utf-8").read()
    assert 'LPP_URL: "./lpp-index.json"' in html       # live view wired
    assert 'DATA_URL: "./tenders.json"' in html
    assert "async function lppLoad" in html            # LPP loader present
    # DPMF export headers shipped in the dashboard's own export:
    assert "DETAILS OF THE LAST PURCHASE" in html
    assert "DPMF 5" in html and "DPMF 7" in html
    assert "5.33.4" in html and "5.32.2" in html


if __name__ == "__main__":
    for n, fn in dict(globals()).items():
        if n.startswith("test_"):
            fn(); print("ok:", n)
    print("ALL LPP INDEX TESTS PASSED")
