"""Thin adapter over the supplied, FINAL `classify.py` (do not modify it).

Maps ProcurementClassifier output onto the record fields the dashboard reads:
criticality / confidence / domains / named_system. Classify on `title`, then
re-run on `title + " " + description` once enriched (item text only — unit/org
is metadata and must never flip the verdict).
"""
from __future__ import annotations

from .classify import ProcurementClassifier

_CLF = ProcurementClassifier()


def classify_text(text: str) -> dict:
    r = _CLF.classify(text or "")
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
