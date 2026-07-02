"""Phase 3 gate: classification wiring.

(1) The supplied classify.py self-test passes (run as-is, unmodified).
(2) A labelled fixture classifies correctly, including the real scraped MES
    title (-> ROUTINE) and the item-not-owner rule (housekeeping for a defence
    lab stays ROUTINE).
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.classify_map import classify_text, classify_record  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_supplied_selftest_passes():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "scraper", "classify.py")],
                         capture_output=True, text=True)
    assert "ALL TESTS PASSED" in out.stdout, out.stdout[-500:]


# (text, expected criticality, expected domain-or-None)
CASES = [
    ("Procurement of UAV ground control station and data terminal", "critical", "UAS"),
    ("Supply of BrahMos missile handling and storage equipment", "critical", None),  # named system
    ("Counter-drone radar (C-UAS) for naval air station", "critical", "C-UAS"),
    ("SIGINT receiver and EW pod calibration", "critical", "EW_SIGINT"),
    ("Quantum key distribution link for secure comms", "critical", "QUANTUM"),
    # ROUTINE — incl. item-not-owner (housekeeping for a defence lab)
    ("Housekeeping and whitewashing services - base buildings", "routine", None),
    ("Housekeeping services for DRDO LRDE Bangalore", "routine", None),
    ("Supply of ration items for station mess", "routine", None),
    # The real scraped tender from the live Home feed (2026-06-28):
    ("REPAIRS TO LEAKAGE/SEEPAGE,PLUMBING AND MISC WORKS AT ZONE-I,II AND VI", "routine", None),
]


def test_labelled_fixture():
    for text, crit, dom in CASES:
        res = classify_text(text)
        assert res["criticality"] == crit, f"{text!r} -> {res}"
        if dom:
            assert dom in res["domains"], f"{text!r} expected domain {dom}, got {res['domains']}"


def test_named_system_sets_confidence_1():
    res = classify_text("Supply of BrahMos missile handling equipment")
    assert res["criticality"] == "critical"
    assert res["named_system"] == "BrahMos"
    assert res["confidence"] == 1.0


def test_naval_establishment_not_critical():
    # 'INS <ship>' is a unit/org name — must NOT flip the verdict (CLAUDE.md rule),
    # even though the FINAL classifier's INS keyword would otherwise match it.
    assert classify_text("Special repairs to Bldg A-84 85 at INS Angre")["criticality"] == "routine"
    assert classify_text("Single living accommodation for sailors at INS Valsura, Jamnagar")["criticality"] == "routine"
    assert classify_text("Repairs to pavers walkway at INS Tunir, Naval Station Karanja")["criticality"] == "routine"
    # a genuine INS (nav-system) item still classifies CRITICAL
    assert classify_text("Supply of INS/GPS module for tactical UAV")["criticality"] == "critical"
    # a real weapon item at a naval ship stays CRITICAL (the item keyword survives)
    assert classify_text("BrahMos handling equipment for INS Vikrant")["criticality"] == "critical"


def test_description_can_upgrade_not_downgrade():
    # Title alone routine-looking; description reveals a CRITICAL item -> upgrade.
    up = classify_record("Annual maintenance contract", "AMC for SIGINT receiver and EW suite")
    assert up["criticality"] == "critical"
    # A critical title is never downgraded by a mundane description.
    keep = classify_record("Supply of BrahMos handling equipment", "delivery to store")
    assert keep["criticality"] == "critical"


if __name__ == "__main__":
    for n, fn in dict(globals()).items():
        if n.startswith("test_"):
            fn(); print("ok:", n)
    print("ALL CLASSIFY TESTS PASSED")
