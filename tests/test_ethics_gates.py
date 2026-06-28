"""Hard-limit enforcement gate (CLAUDE.md scraping-ethics + scope + cost).

These are deterministic CI checks so the non-negotiables can't silently regress:
 - no CAPTCHA-solving / OCR / solver integration anywhere in our code
 - the keyword Search / login / document-download endpoints are *blocked*
 - single source: only defproc.gov.in is crawled
 - forbidden scope (ORBAT / dark-unit / personnel / LinkedIn / satellite geo)
   is not implemented in our code
 - polite crawler: exact descriptive UA (no PII), >= 3 s delay
classify.py is supplied/FINAL and excluded from scope greps (its SPACE/UNIT_ORG
keywords are item-classification metadata, not geolocation/ORBAT features).
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import fetch  # noqa: E402

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scraper")
OUR_SOURCES = [p for p in glob.glob(os.path.join(SCRAPER, "*.py"))
               if os.path.basename(p) != "classify.py"]


def _all_source() -> str:
    return "\n".join(open(p, encoding="utf-8").read() for p in OUR_SOURCES).lower()


def test_no_captcha_solver_or_ocr():
    src = _all_source()
    for tok in ("2captcha", "anti-captcha", "anticaptcha", "deathbycaptcha", "capmonster",
                "pytesseract", "easyocr", "captcha_solver", "solvecaptcha", "solve_captcha",
                "import cv2", "ocr.space"):
        assert tok not in src, f"forbidden CAPTCHA/OCR solver token in source: {tok}"


def test_no_forbidden_scope_code():
    src = _all_source()
    for tok in ("linkedin", "orbat", "order of battle", "order-of-battle", "dark unit",
                "dark-unit", "satellite imagery", "geoint", "facial recognition"):
        assert tok not in src, f"forbidden-scope token in our code: {tok}"


def test_single_source_only():
    src = _all_source()
    for other in ("gem.gov.in", "eprocure.gov.in", "cpppp", "tenderwizard", "bidassist"):
        assert other not in src, f"non-defproc source referenced: {other}"
    assert "defproc.gov.in" in fetch.BASE


def test_gated_endpoints_blocked():
    block = ("https://defproc.gov.in/nicgep/app?page=FrontEndAdvancedSearch&service=page",
             "https://defproc.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
             "https://defproc.gov.in/nicgep/app?service=login",
             "https://defproc.gov.in/nicgep/app?service=download&docId=5")
    for u in block:
        assert fetch.is_forbidden_url(u), f"should be blocked: {u}"
    f = fetch.Fetcher()
    for u in block:
        try:
            f.get(u)
            assert False, f"Fetcher should refuse {u}"
        except fetch.ForbiddenEndpoint:
            pass


def test_open_endpoints_allowed():
    for name in ("home", "by_organisation", "by_location", "archive", "results"):
        u = fetch.BASE + fetch.ENTRY_POINTS[name]
        assert not fetch.is_forbidden_url(u), f"open endpoint wrongly blocked: {name}"


def test_polite_crawler_invariants():
    assert fetch.USER_AGENT == "defproc-monitor/0.1"
    assert "@" not in fetch.USER_AGENT and "gmail" not in fetch.USER_AGENT.lower()  # no PII
    assert fetch.MIN_DELAY >= 3.0
    assert fetch.Fetcher().min_delay >= 3.0


def test_captcha_wall_detector():
    # incidental widget (real content present) -> not walled
    assert not fetch.looks_like_captcha_wall("<table class='td_caption'>Enter Captcha ... Tender Title</table>")
    # pure challenge -> walled
    assert fetch.looks_like_captcha_wall("<div>Enter Captcha</div><div>Provide Captcha and click Search</div>")


if __name__ == "__main__":
    for n, fn in dict(globals()).items():
        if n.startswith("test_"):
            fn(); print("ok:", n)
    print("ALL ETHICS GATE TESTS PASSED")
