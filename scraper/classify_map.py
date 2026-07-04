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
_AMBIGUOUS = {
    # acronyms colliding with everyday usage
    "smart", "ins", "csr", "pqc", "satcom", "pa", "ti", "io", "es", "ea", "ep",
    "df", "c2", "cop", "bms", "cms", "adc", "dsp", "atr", "mda", "fpa", "lna",
    "twt", "aoa", "daa", "tes", "boss",
    # generic English words in the keyword sets
    "launcher", "magazine", "seeker", "interceptor", "swarm", "swarming",
    "generator", "certification", "qualification", "telemetry", "annotation",
    "rocket", "constellation", "gimbal", "autopilot", "catapult", "flare",
    "decoy", "beacon", "transponder", "interrogator", "radome", "fuel cell",
    # named systems that are common Indian names/words (buildings, messes, roads)
    "rajendra", "bharat", "drishti", "netra", "netro", "akash", "shakti",
    "indra", "abhay", "kavach", "sanket", "tarang", "ajanta", "bharani",
    "rohini", "ashwini", "revathi", "aslesha", "tempest", "porpoise", "archer",
    "lakshya", "nishant", "rustom", "tapas", "ghatak", "muntra", "agni",
    "prithvi", "nag", "astra", "pralay", "prahaar", "barak", "samar",
    "trishul", "coral",
}

# strong civil-works signals (MES vocabulary) — presence marks repair/estate work
_CIVIL = re.compile(
    r"\b(repairs?|maint|maintenance|whitewash\w*|painting|distemper\w*|plumbing|"
    r"sewage|sanitary|drainage|roofing|flooring|fencing|boundary wall|compound wall|"
    r"accn|bldgs?|buildings?|quarters|accommodation|barracks?|mess|canteen|toilets?|"
    r"roads?|pavement|culverts?|footpath|hardstanding|water supply|pipe ?lines?|pumps?|"
    r"septic|manholes?|electric(?:al)? works?|wiring|tube lights?|street lights?|fans?|"
    r"coolers?|furniture|conservancy|housekeeping|horticulture|garden\w*|term contract|"
    r"artificer|renovation|upgradation|improvement|sheds?|chajjas?|welcome maint)\b", re.I)


def _gate(r, text: str) -> dict:
    out = {
        "criticality": r.classification.lower(),
        "confidence": round(float(r.confidence), 2),
        "domains": list(r.domains),
        "named_system": r.named_system_match,
    }
    if out["criticality"] != "critical":
        return out
    matched = [k.lower().replace("[system] ", "") for k in r.matched_keywords]
    unambiguous = [k for k in matched if k not in _AMBIGUOUS]
    if unambiguous:
        return out
    if _CIVIL.search(text or ""):
        return {"criticality": "routine", "confidence": 0.75,
                "domains": [], "named_system": None}
    return out


def classify_text(text: str) -> dict:
    clean = _declutter(text)
    return _gate(_CLF.classify(clean), clean)


def classify_record(title: str, description: str = "") -> dict:
    """Classify on title; with a description, classify on title+description and
    trust that verdict — the combined text is a superset, so unambiguous title
    evidence always survives, while the gate can veto ambiguous-only hits once
    the description reveals civil-works context (Layer 2 verify)."""
    desc = (description or "").strip()
    if desc and desc.lower() != (title or "").strip().lower():
        return classify_text(f"{title} {description}")
    return classify_text(title)
