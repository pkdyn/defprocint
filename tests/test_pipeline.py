"""Phase gate: end-to-end live pipeline on fixtures (offline, deterministic).

Exercises collect_recent_rows (org tree -> org listing -> published filter) ->
enrich -> classify(title+desc) -> geocode(triangulate) -> assemble -> diff,
and asserts the dashboard data contract (incl. `published` + stable detail_url).
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.fetch import TENDER_LOOKUP_URL  # noqa: E402
from scraper.pipeline import run_live, CONTRACT_FIELDS  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

# minimal org-tree: one org whose tender-count ("71") links to its listing page
ORG_TREE = ('<html><body><table><tr><td>'
            '<a href="https://defproc.gov.in/nicgep/app?component=$DirectLink&page='
            'FrontEndTendersByOrganisation&service=direct&session=T&sp=ORGLIST">71</a>'
            '</td></tr></table></body></html>')


class _Resp:
    def __init__(self, text):
        self.text = text


class FixtureFetcher:
    def __init__(self):
        self.count = 0
        self._org = open(os.path.join(FIX, "live_org_listing.html"), encoding="utf-8").read()
        self._detail = open(os.path.join(FIX, "live_detail.html"), encoding="utf-8").read()

    def get(self, url):
        self.count += 1
        if "FrontEndTendersByOrganisation" in url and "service=page" in url:
            return _Resp(ORG_TREE)
        if "ORGLIST" in url:
            return _Resp(self._org)
        return _Resp(self._detail)  # any $DirectLink detail


def test_pipeline_recent_publish_window_and_contract():
    # huge window so every fixture row counts as "recent" regardless of its date
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "tenders.json")
        recs = run_live(FixtureFetcher(), out_path=out, retention_hours=10_000_000,  # type: ignore[arg-type]
                        max_enrich=1, now=datetime(2026, 6, 28, tzinfo=timezone.utc))
        assert json.load(open(out, encoding="utf-8")) == recs

    assert len(recs) >= 20, f"expected the org's tenders, got {len(recs)}"
    ids = [r["tender_id"] for r in recs]
    assert len(ids) == len(set(ids)), "duplicate tender_id"

    for r in recs:
        for f in CONTRACT_FIELDS:
            assert f in r, f"missing contract field {f}"
        assert r["criticality"] in ("critical", "routine")
        assert r["published"].endswith("Z"), r["published"]   # published drives the window
        assert r["detail_url"] == TENDER_LOOKUP_URL            # stable public link, not a session URL

    # the one enriched record carries the real canonical id + buyer block
    enriched = [r for r in recs if r["tender_id"] == "2026_MES_775135_1"]
    assert enriched, "expected the enriched detail record"
    assert enriched[0]["pincode"] == "786189"


if __name__ == "__main__":
    test_pipeline_recent_publish_window_and_contract()
    print("ALL PIPELINE TESTS PASSED")
