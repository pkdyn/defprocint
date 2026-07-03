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


def classify_text(text: str) -> dict:
    r = _CLF.classify(_declutter(text))
    return {
        "criticality": r.classification.lower(),  # 'critical' | 'routine'
        "confidence": round(float(r.confidence), 2),
        "domains": list(r.domains),
        "named_system": r.named_system_match,
    }


def classify_record(title: str, description: str = "") -> dict:
    """Classify on title; if a description adds CRITICAL signal, prefer the
    richer (title+description) verdict. Never let a description downgrade."""
    base = classify_text(title)
    desc = (description or "").strip()
    if desc and desc.lower() != (title or "").strip().lower():
        combined = classify_text(f"{title} {description}")
        if combined["criticality"] == "critical" and base["criticality"] != "critical":
            return combined
        if base["criticality"] == "critical" and combined["criticality"] == "critical":
            # keep the more-informative (more domains / named system) result
            return combined if len(combined["domains"]) >= len(base["domains"]) else base
    return base
