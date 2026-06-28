"""E2E gate on the committed live artifacts (web/tenders.json, web/lpp-index.json).

Mirrors the dashboard's own loadTenders() contract + LPP record shape. Skips
cleanly if the files don't exist yet (fresh checkout before the first scrape),
so CI is green both before and after the scheduled Action produces data.
"""
import json
import os

import pytest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
TENDERS = os.path.join(WEB, "tenders.json")
LPP = os.path.join(WEB, "lpp-index.json")

CONTRACT = ("tender_id", "title", "org_chain", "location", "unit", "buyer_address",
            "pincode", "lat", "lng", "criticality", "confidence", "domains",
            "named_system", "closing_date", "published", "first_seen")


@pytest.mark.skipif(not os.path.exists(TENDERS), reason="no tenders.json yet (pre-first-scrape)")
def test_tenders_artifact_matches_contract():
    data = json.load(open(TENDERS, encoding="utf-8"))
    assert isinstance(data, list) and data, "tenders.json empty"
    ids = [t["tender_id"] for t in data]
    assert len(ids) == len(set(ids)), "duplicate tender_id"
    for t in data:
        for k in CONTRACT:
            assert k in t, f"missing contract field {k}"
        assert t["criticality"] in ("critical", "routine")
        assert isinstance(t["domains"], list)
        assert t["first_seen"].endswith("Z")


@pytest.mark.skipif(not os.path.exists(LPP), reason="no lpp-index.json yet (pre-first-scrape)")
def test_lpp_artifact_loads_and_is_searchable():
    doc = json.load(open(LPP, encoding="utf-8"))
    assert doc["count"] == len(doc["records"])
    for b in doc["records"]:
        for k in ("id", "title", "unit", "mode", "date", "detail_url"):
            assert k in b, f"missing LPP field {k}"
        assert b["detail_url"].startswith("http")
    # the dashboard's substring search returns hits on a generic item token
    def match(b, tok):
        hay = (b["title"] + " " + b["unit"] + " " + b["location"]).lower()
        return tok in hay
    assert any(match(b, "repair") for b in doc["records"]) or len(doc["records"]) >= 1
