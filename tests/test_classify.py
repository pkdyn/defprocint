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


def test_place_context_system_names_not_critical():
    # Real user-reported false positives (2026-06-29): system names appearing as
    # PLACE/UNIT/FACILITY names or everyday adjectives must not flip the verdict.
    routine = [
        "SPECIAL REPAIR REPLACEMENT OF CONVENTIONAL TUBE LIGHTS WITH ALLIED WORKS AT C BAND SATCOM UPS ROOM AC FOR SIGNAL EQUIPMENT ROOM",
        "SMART PERIODICAL AND MISC REPAIRS INCL CHAJJAS, MULTISTOREY BLDGS UNDER GE (WEST) BAREILLY",
        "REPAIR/MAINTENANCE OF STREET LIGHTS AND CONNECTED ITEMS OF DRDL, ASL, NGARM AND QRSAM AREA UNDER GE (I) RND KANCHANBAGH",
        "SPECIAL REPAIRS TOWARDS REPLACEMENT OF ALL EXISTING METERS WITH SMART PREPAID METERS INCLUDING SERVER",
        "CAMOUFLAGE PAINTING WITH SMART PERIODICAL METHODOLOGY TO CERTAIN BLDGS AT AF STN BIKANER",
        "UPGRADATION OF VIP ROOMS OF TRISHUL OFFICERS MESS AT HQ WAC SUBROTO PARK",
        "REPAIR/ REPLACEMENT OF SEWAGE LINES AT 21 CSR DRONACHAL BASE UNDER GE DRONACHAL",
        "SMART WELCOME MAINT OF OFFICERS, JCOS/OR, CIV MD ACCN AND CERTAIN ALLIED WORKS IN MES AT DAPPAR",
        "PROVISION OF SMART CLASSROOM EQUIPMENT AT ARMY SCHOOL",
        "PROVN OF HOT WATER GENERATOR FOR CERTAIN BLDGS AT BB CANTT, SRINAGAR",
        "TERM CONTRACT FOR ARTIFICER WORK FOR RAJENDRA NAGAR, AT LONAVLA",
    ]
    for t in routine:
        assert classify_text(t)["criticality"] == "routine", t[:60]
    # Genuine critical items keep their verdicts (declutter must not over-strip):
    critical = [
        "Procurement of QRSAM missile system spares",
        "SMART missile test support equipment",
        "SMART torpedo handling and storage equipment",
        "SATCOM terminal for tactical communications",
        "Supply of diesel generator 250 KVA for radar site",  # power genset = ENABLERS by taxonomy
        "Supply of INS/GPS module for tactical UAV",
    ]
    for t in critical:
        assert classify_text(t)["criticality"] == "critical", t[:60]


def test_ambiguity_gate():
    # Layer 1: ambiguous-only evidence + civil-works context -> vetoed to ROUTINE
    routine = [
        "REPAIR OF PA SYSTEM AT PARADE GROUND",                    # 'PA' acronym
        "WHITEWASHING OF LAKSHYA INSTITUTE BUILDING",              # named system as building name
        "MAINT OF ROADS NEAR TAPAS ENCLAVE",                       # named system as enclave name
        "PROVN OF FURNITURE FOR AGNI BLOCK QUARTERS",              # named system as block name
    ]
    for t in routine:
        assert classify_text(t)["criticality"] == "routine", t
    # ambiguous-only WITHOUT civil context -> verdict stands (precision, not blindness)
    critical = [
        "Procurement of Astra missile seekers",                    # ambiguous named + seeker, no civil
        "SMART torpedo handling and storage equipment",
        "Supply of diesel generator 250 KVA for radar site",
    ]
    for t in critical:
        assert classify_text(t)["criticality"] == "critical", t
    # >=1 unambiguous keyword always stands, even inside civil phrasing
    assert classify_text("Repair of night vision devices")["criticality"] == "critical"
    assert classify_text("AMC for SIGINT receiver and EW suite")["criticality"] == "critical"


def test_unit_designation_system_names_vetoed():
    # AREN/ASCON/CIDSS as unit/store designations + medical 'PA' ref-titles
    # (real Jul-4 false positives caught in live data)
    assert classify_text("COMPREHENSIVE MAINTENANCE WORK TO OTM ACCN 21 CSR (AREN) AT DRONACHAL BASE")["criticality"] == "routine"
    assert classify_text("PROVN OF MT SHED FOR CIDSS AND FCC VEH")["criticality"] == "routine"
    assert classify_text("2433/MS/EXP/Onco Surg/Drugs/PAC PA 497/2026-27")["criticality"] == "routine"  # 'drugs' civil
    assert classify_text("INVITATION OF BIDS FOR REPAIR OF 01 NIV EXPENDABLE MEDICAL STORE")["criticality"] == "routine"


def test_rich_signal_lone_ambiguous_vetoed():
    # With a full description (Layer-2), ONE lone ambiguous token = noise...
    assert classify_record("81203/OBM PA/ENGR/0079",
                           "SUPPLY OF ENGINE SPARES FOR SCANIA TIPPER TRUCK")["criticality"] == "routine"
    assert classify_record("EP/D-26/170/2026-27",
                           "PROCUREMENT OF EXPENDABLE STORES FOR WORKSHOP")["criticality"] == "routine"
    # ...but two distinct ambiguous tokens corroborate each other and stand
    assert classify_record("Spares for Akash launcher unit",
                           "supply of spares for Akash launcher")["criticality"] == "critical"
    # and an unambiguous item in the description always stands
    assert classify_record("EP/D-26/171/2026-27",
                           "procurement of thermal imager sights")["criticality"] == "critical"


def test_verify_desc_can_veto_ambiguous_title():
    # Layer 2 semantics: a title-critical on ambiguous-only evidence is re-judged
    # on title+description; civil-works description vetoes it.
    r = classify_record("Provision of launcher spares",
                        "REPAIRS TO LEAKAGE/SEEPAGE, PLUMBING AND MISC WORKS AT ZONE-I")
    assert r["criticality"] == "routine"
    # ...but an unambiguous item in the title survives any description
    r2 = classify_record("Supply of thermal imager",
                         "repairs to building and whitewashing of store")
    assert r2["criticality"] == "critical"


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
