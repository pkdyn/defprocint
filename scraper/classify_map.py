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

# 'INS <ship/estt name>' is a naval UNIT/ORG reference (INS Valsura, INS Angre) —
# CLAUDE.md: unit/org is metadata only and must never flip the verdict. Left in,
# it false-triggers the FINAL classifier's INS (inertial-navigation-system)
# keyword and tags every naval civil-works tender CRITICAL. We strip it BEFORE
# classifying (classify.py is untouched). Real INS items survive: 'INS/GPS',
# 'INS-GNSS', 'inertial navigation system' have no space-then-name after INS.
_SHIP_REF = re.compile(r"\bINS\s+[A-Za-z][\w()&.'-]*", re.I)


def _declutter(text: str) -> str:
    return _SHIP_REF.sub(" ", text or "")


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
