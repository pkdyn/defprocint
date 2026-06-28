"""LPP search behaviour — which keyword combinations actually return archive/LPP
hits. Mirrors the dashboard's `lppMatch()` (whitespace-tokenised, AND-of-substrings
over title+domains+named+unit+location) against a corpus of real defproc-style
titles, so the keyword learnings are pinned down deterministically.

Key findings encoded here (verified against live defproc data 2026-06-28):
 - Search the ITEM KEYWORD, not the full phrase: GePNIC titles rarely contain the
   word "procurement"/"hiring", so a multi-word phrase AND-matches to nothing.
 - "amc" is NOISY: it matches both Annual-Maintenance-Contract *and* "Army Medical
   Corps / AMC unit". Narrow with "amc for" / "annual maintenance".
 - "it" is a dangerous token (substring of "un**it**", etc.).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.index_lpp import to_lpp_record  # noqa: E402

# Representative real-style defproc titles (drawn from the live catalogue).
RAW = [
    ("P1", "REPAIR AND MAINTENANCE TO VARIOUS TYPE OF PRINTER"),
    ("P2", "ANNUAL MAINTENANCE CONTRACT FOR COMPUTERS AND PRINTERS"),
    ("X1", "AMC FOR XEROX BRAND PHOTOCOPIERS"),
    ("M1", "PETTY REPAIRS AND DAY TO DAY COMPLAINTS TO MH AND AMC UNIT"),  # AMC = Army Medical Corps
    ("IT1", "HIRING OF IT INFRASTRUCTURE INCL AMC SERVICES"),
    ("O1", "REPAIR OF OTDR MACHINE FOR OFC NETWORK"),
]
CORPUS = [to_lpp_record({"tender_id": tid, "title": t, "criticality": "routine",
                         "closing_iso": "2026-07-10"}) for tid, t in RAW]


def search(query):
    """Exact mirror of the dashboard lppMatch + lppSearch tokenisation."""
    tokens = [t for t in query.lower().split() if t]
    out = []
    for b in CORPUS:
        hay = (b["title"] + " " + " ".join(b.get("domains") or []) + " "
               + (b.get("named") or "") + " " + b["unit"] + " " + b["location"]).lower()
        if all(t in hay for t in tokens):
            out.append(b["id"])
    return set(out)


def test_printer_keyword_beats_phrase():
    assert search("printer") == {"P1", "P2"}          # keyword works
    assert search("printer procurement") == set()     # phrase fails (no "procurement")
    assert search("procurement of printer") == set()


def test_otdr_phrase_works_only_if_item_present():
    assert search("otdr") == {"O1"}
    assert search("otdr machine") == {"O1"}
    assert search("repair of otdr machine") == {"O1"}  # all tokens present in O1


def test_amc_is_noisy_narrow_it():
    # bare "amc" mixes maintenance contracts AND the Army Medical Corps unit
    assert search("amc") == {"X1", "M1", "IT1"}
    # narrowing recovers the real maintenance contract
    assert search("amc for") == {"X1"}
    assert search("annual maintenance") == {"P2"}


def test_it_amc_combinations():
    # "it amc" catches IT1 but also M1 (because "un-IT" contains "it" + has AMC)
    assert "IT1" in search("it amc")
    assert "M1" in search("it amc")          # demonstrates the "it" substring noise
    # the full phrase narrows to the genuine IT-AMC tender
    assert search("hiring of it amc") == {"IT1"}


def test_amc_services_combinations():
    assert search("hiring of amc services") == {"IT1"}
    assert search("amc services") == {"IT1"}


if __name__ == "__main__":
    for n, fn in dict(globals()).items():
        if n.startswith("test_"):
            fn(); print("ok:", n)
    print("ALL LPP SEARCH TESTS PASSED")
