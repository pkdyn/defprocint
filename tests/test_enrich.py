"""Phase 2 gate: detail-page enrichment + graceful degradation + personnel guard."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.enrich import enrich_record, derive_unit, synth_tender_id  # noqa: E402
from scraper.fetch import ForbiddenEndpoint  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class _Resp:
    def __init__(self, text):
        self.text = text


class StubFetcher:
    """Returns a fixture for any URL (no network)."""
    def __init__(self, name):
        with open(os.path.join(FIX, name), encoding="utf-8") as f:
            self._html = f.read()

    def get(self, url):
        return _Resp(self._html)


class GatedFetcher:
    def get(self, url):
        raise ForbiddenEndpoint("policy: refusing gated endpoint")


class BoomFetcher:
    def get(self, url):
        raise ConnectionError("network down")


ROW = {"title": "REPAIRS TO LEAKAGE/SEEPAGE", "ref_no": "8969/E8",
       "closing_date": "18 Jul", "detail_url": "https://defproc.gov.in/x"}


def test_good_detail_fills_buyer_block():
    rec = enrich_record(StubFetcher("live_detail.html"), ROW)
    assert rec["enriched"] is True
    assert rec["tender_id"] == "2026_MES_775135_1"
    assert rec["pincode"] == "786189"
    assert "Garrison Engineer" in rec["unit"]
    assert rec["buyer_address"]
    assert rec["value_inr"] == 1700000
    assert "▸" in rec["org_chain"]


def test_gated_detail_degrades():
    rec = enrich_record(GatedFetcher(), ROW)
    assert rec["enriched"] is False
    assert rec["tender_id"].startswith("LIST_")  # synthesised, stable
    assert rec["title"] == ROW["title"]          # listing record kept
    assert rec["pincode"] == ""                  # buyer field skipped, no crash


def test_network_error_degrades():
    rec = enrich_record(BoomFetcher(), ROW)
    assert rec["enriched"] is False
    assert rec["title"] == ROW["title"]


def test_captcha_search_page_degrades():
    # A page with no canonical tender id (the Active-Tenders CAPTCHA search form).
    rec = enrich_record(StubFetcher("live_latest_active.html"), ROW)
    assert rec["enriched"] is False
    assert rec["pincode"] == ""


def test_tia_name_shown_verbatim():
    # Safeguard removed by design: surface the TIA name exactly as defproc
    # publishes it (appointment OR officer name/rank) so the exposure is visible.
    org = "Ministry of Defence ▸ Indian Navy ▸ Naval Dockyard (Mumbai)"
    assert derive_unit("Garrison Engineer Dinjan No 02", org) == "Garrison Engineer Dinjan No 02"
    assert derive_unit("Commanding Officer INS Valsura", org) == "Commanding Officer INS Valsura"
    assert derive_unit("Cdr R K Sharma", org) == "Cdr R K Sharma"        # name shown as-is
    assert derive_unit("Col A. K. Singh", org) == "Col A. K. Singh"
    assert derive_unit("Vikram Menon", org) == "Vikram Menon"
    # Only when defproc gives no name at all do we fall back to the org tail.
    assert derive_unit("", org) == "Naval Dockyard (Mumbai)"


def test_synth_id_stable_and_unique():
    a = synth_tender_id(ROW)
    b = synth_tender_id(ROW)
    c = synth_tender_id({"title": "OTHER", "ref_no": "9131"})
    assert a == b and a != c and a.startswith("LIST_")


if __name__ == "__main__":
    g = dict(globals())
    for n, fn in g.items():
        if n.startswith("test_"):
            fn(); print("ok:", n)
    print("ALL ENRICH TESTS PASSED")
