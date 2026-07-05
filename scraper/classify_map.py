"""Thin adapter over the supplied, FINAL `classify.py` (do not modify it).

Maps ProcurementClassifier output onto the record fields the dashboard reads:
criticality / confidence / domains / named_system. Classify on `title`, then
re-run on `title + " " + description` once enriched (item text only — unit/org
is metadata and must never flip the verdict).
"""
from __future__ import annotations

import re

from .classify import ProcurementClassifier

_CLF = ProcurementClassifier()

# CLAUDE.md rule: unit/org/place names are metadata only and must never flip a
# verdict. Real MES/civil-works titles routinely reference system names as PLACE,
# UNIT or FACILITY names ("QRSAM AREA", "TRISHUL OFFICERS MESS", "21 CSR ...
# BASE", "INS Valsura"), and everyday adjectives collide with system names
# ("SMART prepaid meters" vs the SMART torpedo). We strip these location/
# collocation contexts BEFORE classifying — classify.py itself stays untouched.
# Genuine items survive: "QRSAM missile", "SMART missile", "SATCOM terminal",
# "INS/GPS module" contain none of these context patterns.
_DECLUTTER = [
    # naval ship / establishment: INS <Name>  (INS/GPS, INS-GNSS unaffected)
    re.compile(r"\bINS\s+[A-Za-z][\w()&.'-]*", re.I),
    # system name used as an area / mess / colony / base qualifier
    re.compile(r"\b(?:QRSAM|MRSAM|LRSAM|VSHORAD|AKASH|TRISHUL|BRAHMOS|AGNI|PRITHVI|NAG|"
               r"PINAKA|RAJENDRA|SAMAR|CSR)\s+(?:OFFICERS\s+)?"
               r"(?:AREA|NAGAR|MESS|VIHAR|BLOCK|GATE|CAMP|BASE|ENCLAVE|COMPLEX|COLONY)\b", re.I),
    # '<number> CSR' is a unit designation (21 CSR), not a surveillance radar
    re.compile(r"\b\d+\s+CSR\b", re.I),
    # 'smart' is an everyday adjective (smart meters/welcome/city/…). Keep it ONLY
    # in weapon context — the real SMART is DRDO's missile-launched torpedo, so a
    # genuine tender says "SMART missile/torpedo/system/…". Everything else strips.
    re.compile(r"\bSMART\b(?!\s+(?:MISSILE|TORPEDO|WEAPON|SYSTEM|LAUNCHERS?|MUNITION|TEST))", re.I),
    # hot-water generator = a boiler, not a power generator (ENABLERS keyword)
    re.compile(r"\bHOT\s+WATER\s+GENERATORS?\b", re.I),
    # SATCOM named as a room/building the works happen AT (item = the works)
    re.compile(r"\b(?:[A-Z]{1,3}\s+BAND\s+)?SATCOM(?:\s+\w+){0,2}\s+ROOMS?\b", re.I),
    # 'firing range' is estate/infrastructure — repairing/fencing/cleaning it is
    # civil works. A genuine range-instrumentation tender still hits radar/sensor.
    re.compile(r"\bfiring\s+ranges?\b", re.I),
    # 'EW' as a unit designation / building number / project name, NOT electronic
    # warfare: '8 EW', 'EW-175', 'EW BDE/BN/COY', 'EW PROJECT'. 'EW SYSTEM'/'EW
    # SUITE'/'EW SPARES' carry their own keyword and survive.
    re.compile(r"\b\d+\s*EW\b|\bEW\s*[-–]\s*\d+\b|"
               r"\bEW\s+(?:BDE|BN|COY|EME|BRIGADE|REGT|REGIMENT|PROJECT|SIGNAL)\b", re.I),
    # named systems used as a POST / vehicle / centre name, not the weapon
    re.compile(r"\bSHIV\s+SHAKTI\b|\bMARUTI\s+SWIFT\b", re.I),
    # 'Army Air Defence Centre/College' is the formation NAME (accn/works there
    # stays routine); a real AD radar/missile tender hits its own keyword
    re.compile(r"\b(?:ARMY\s+)?AIR\s+DEFENCE\s+(?:CENTRE|COLLEGE|SCHOOL)\b|"
               r"\bAAD\s+(?:CENTRE|COLLEGE|COL)\b", re.I),
]


def _declutter(text: str) -> str:
    out = text or ""
    for pat in _DECLUTTER:
        out = pat.sub(" ", out)
    return out


# ---------------------------------------------------------------------------
# Ambiguity gate (Layer 1). The FINAL classifier flips CRITICAL on ANY single
# keyword hit. Some of its keywords are polysemous in Indian-MoD tender prose —
# short acronyms that double as everyday terms, and named systems that are
# common Indian names/words used for buildings, messes and enclaves. Gate rule:
#   * >=1 UNAMBIGUOUS critical keyword         -> CRITICAL stands
#   * only ambiguous hits + civil-works context -> vetoed to ROUTINE
#   * only ambiguous hits, no civil context     -> CRITICAL stands
# Known tradeoff (accepted, precision-first): a genuine critical described ONLY
# by ambiguous words inside civil phrasing ("repair of Akash launcher") is
# vetoed; Layer 2's description re-check runs through this same gate.
# ---------------------------------------------------------------------------
# Tier-1 WEAK tokens: short acronyms / utility phrases that collide with unit
# designations, building numbers, place names and estate services. Unlike the
# tier-2 set below, a LONE weak hit is NEVER enough for CRITICAL (even title-only)
# — these are only ever critical when a genuine keyword co-occurs. Verified false
# positives: 'HQ IDS' (Integrated Defence Staff), '1 EW BDE' sewage, 'MCC PANEL'
# (motor control centre), 'SCADA' pump control, 'ES NETWORK' (electrical supply),
# 'GCS MESS', 'SOC' accn, 'ITR' artificer works, 'Project Beacon' road, rooftop
# 'solar panel', AC 'cooling system', EV 'charging station'.
_WEAK = {
    "ids", "es", "ew", "mcc", "scada", "soc", "gcs", "itr", "beacon",
    "qualification", "solar panel", "cooling system", "charging station",
    # network/C4ISR names that surface as PROJECT / store / unit designations in
    # MES civil works ('Project ASCON power supply', '21 CSR (AREN)', 'CIDSS shed')
    "aren", "ascon", "cidss", "afnet", "expendable",
}

_AMBIGUOUS = {
    # acronyms colliding with everyday usage
    "smart", "ins", "csr", "pqc", "satcom", "pa", "ti", "io", "ea", "ep",
    "df", "c2", "cop", "bms", "cms", "adc", "dsp", "atr", "mda", "fpa", "lna",
    "twt", "aoa", "daa", "tes", "boss", "tip",
    # generic English words in the keyword sets
    "launcher", "magazine", "seeker", "interceptor", "swarm", "swarming",
    "generator", "certification", "telemetry", "annotation",
    "rocket", "constellation", "gimbal", "autopilot", "catapult", "flare",
    "decoy", "transponder", "interrogator", "radome", "fuel cell",
    # named systems that are common Indian names/words (buildings, messes, roads)
    "rajendra", "bharat", "drishti", "netra", "netro", "akash", "shakti",
    "indra", "abhay", "kavach", "sanket", "tarang", "ajanta", "bharani",
    "rohini", "ashwini", "revathi", "aslesha", "tempest", "porpoise", "archer",
    "lakshya", "nishant", "rustom", "tapas", "ghatak", "muntra", "agni",
    "prithvi", "nag", "astra", "pralay", "prahaar", "barak", "samar",
    "trishul", "coral",
    # higher C4ISR/air-defence system names (genuine when procured as equipment)
    "iaccs", "nc3i", "nmda",
}

# strong civil-works signals (MES vocabulary) — presence marks repair/estate work
_CIVIL = re.compile(
    r"\b(repairs?|maint|maintenance|whitewash\w*|painting|distemper\w*|plumbing|"
    r"sewage|sanitary|drainage|roofing|flooring|fencing|boundary wall|compound wall|"
    r"accn|bldgs?|buildings?|quarters|accommodation|barracks?|mess|canteen|toilets?|"
    r"roads?|pavement|culverts?|footpath|hardstanding|water supply|pipe ?lines?|pumps?|"
    r"septic|manholes?|electric(?:al)? works?|wiring|tube lights?|street lights?|fans?|"
    r"coolers?|furniture|conservancy|housekeeping|horticulture|garden\w*|term contract|"
    r"artificer|renovation|upgradation|improvement|sheds?|chajjas?|welcome maint|"
    # medical / provisioning routine contexts (ECHS drugs, hospital stores, rations)
    r"drugs?|medical|medicines?|hospital|surgical|dental|polyclinic|veterinary|"
    r"dietary|reagents?|rations?|workshop|leasing|leased?)\b", re.I)


_VETOED = {"criticality": "routine", "confidence": 0.75, "domains": [], "named_system": None}


def _gate(r, text: str, rich: bool = False) -> dict:
    """rich=True means the full description is available (Layer-2 verified). A
    genuine system tender's description names real items, so with rich signal a
    LONE ambiguous token is treated as noise; two distinct ambiguous tokens
    co-occurring ("Akash launcher") still corroborate each other and stand."""
    out = {
        "criticality": r.classification.lower(),
        "confidence": round(float(r.confidence), 2),
        "domains": list(r.domains),
        "named_system": r.named_system_match,
    }
    if out["criticality"] != "critical":
        return out
    matched = [k.lower().replace("[system] ", "") for k in r.matched_keywords]
    # a genuine critical keyword (neither weak nor ambiguous) always stands
    strong = [k for k in matched if k not in _AMBIGUOUS and k not in _WEAK]
    if strong:
        return out
    # only ambiguous/weak evidence remains
    if _CIVIL.search(text or ""):
        return dict(_VETOED)
    named = [k for k in matched if k in _AMBIGUOUS]  # tier-2 CAN stand alone ('Rohini radar')
    if not named:                                    # only tier-1 weak acronyms -> never critical
        return dict(_VETOED)
    if rich and len(set(named)) <= 1:                # lone tier-2 token + full desc = noise
        return dict(_VETOED)
    return out


def classify_text(text: str, rich: bool = False) -> dict:
    clean = _declutter(text)
    return _gate(_CLF.classify(clean), clean, rich=rich)


def classify_record(title: str, description: str = "") -> dict:
    """Classify on title; with a description, classify on title+description and
    trust that verdict — the combined text is a superset, so unambiguous title
    evidence always survives, while the gate can veto ambiguous-only hits once
    the description reveals civil/medical context or adds no real item words."""
    desc = (description or "").strip()
    if desc and desc.lower() != (title or "").strip().lower():
        return classify_text(f"{title} {description}", rich=True)
    return classify_text(title)
