"""Idempotent diff + retention against the previously committed tenders.json.

- New tender_id  -> set first_seen = last_seen = now, status 'active'.
- Seen tender_id -> keep first_seen, refresh last_seen + mutable fields.
- Never duplicate a tender_id.
- Retain records whose first_seen is within RETENTION_HOURS + BUFFER_HOURS
  (served file = 72 h live window + small buffer so brief gaps don't drop edges;
  the dashboard itself filters to exactly 72 h on load).
"""
from __future__ import annotations

from datetime import datetime, timezone

RETENTION_HOURS = 72
BUFFER_HOURS = 48  # served file keeps 72 + 48 = 120 h (5 days)

# Fields refreshed on re-sighting (first_seen is immutable; identity is tender_id).
_MUTABLE = ("title", "org_chain", "location", "unit", "buyer_address", "pincode",
            "lat", "lng", "criticality", "confidence", "domains", "named_system",
            "closing_date", "published", "value_inr", "tender_type", "category",
            "detail_url", "status")


def iso_now(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def merge_and_retain(new_records, existing_records, now=None,
                     retention_hours=RETENTION_HOURS, buffer_hours=BUFFER_HOURS):
    """Return the merged, deduped, retention-filtered record list."""
    now = now or datetime.now(timezone.utc)
    now_iso = iso_now(now)
    keep_seconds = (retention_hours + buffer_hours) * 3600

    by_id: dict[str, dict] = {}
    for rec in existing_records or []:
        tid = rec.get("tender_id")
        if tid:
            by_id[tid] = dict(rec)

    for rec in new_records or []:
        tid = rec.get("tender_id")
        if not tid:
            continue
        if tid in by_id:
            cur = by_id[tid]
            for k in _MUTABLE:
                if k in rec and rec[k] not in (None, "", []):
                    cur[k] = rec[k]
            cur["last_seen"] = now_iso
            cur.setdefault("first_seen", now_iso)
        else:
            r = dict(rec)
            r.setdefault("status", "active")
            r["first_seen"] = now_iso
            r["last_seen"] = now_iso
            by_id[tid] = r

    out = []
    for rec in by_id.values():
        # Retain by e-Published date (novelty window); fall back to first_seen
        # for records that predate the published field.
        ts = parse_iso(rec.get("published") or rec.get("first_seen", ""))
        if ts is None:
            rec.setdefault("first_seen", now_iso)
            out.append(rec)
            continue
        if (now - ts).total_seconds() <= keep_seconds:
            out.append(rec)
    out.sort(key=lambda r: (r.get("criticality") != "critical", r.get("first_seen", "")), reverse=False)
    return out
