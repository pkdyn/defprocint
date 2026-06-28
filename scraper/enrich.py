"""Bounded detail-page enrichment: follow a listing row's detail_url and fill
unit / buyer_address / pincode / org_chain / value / type / description.

Graceful degradation (hard rule): if the detail page is gated (CAPTCHA/login),
forbidden by policy, errors, or yields no canonical tender id, we KEEP the
listing-level record (synthesising a stable tender_id) and skip only the buyer
block — never crash the run.

Tender Inviting Authority name (verbatim, by design): `derive_unit()` surfaces
the GePNIC "Tender Inviting Authority -> Name" EXACTLY as defproc publishes it on
its public detail page — appointment ("Garrison Engineer Dinjan No 02") or, where
the portal exposes it, an officer's name/rank. This is intentional: the project
exists to show what is already openly published, so the exposure is visible to
the concerned authorities and can be fixed. We still never CORRELATE a name
across other sources / social media — only the published contact is shown.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import timedelta

from . import parse as P
from .fetch import ForbiddenEndpoint, GatedContent

_IST = timedelta(hours=5, minutes=30)  # defproc publishes wall-clock IST


def _published_iso(row: dict) -> str:
    """e-Published datetime (IST) -> UTC ISO 8601, for novelty/retention."""
    pdt = row.get("published_dt")
    return (pdt - _IST).strftime("%Y-%m-%dT%H:%M:%SZ") if pdt else ""

log = logging.getLogger("defproc.enrich")


def org_tail(org_chain: str) -> str:
    parts = [p.strip() for p in (org_chain or "").split("▸") if p.strip()]
    return parts[-1] if parts else ""


def derive_unit(tia_name: str, org_chain: str) -> str:
    """Return the Tender Inviting Authority name exactly as defproc publishes it.

    No redaction: the published name (appointment or officer name/rank) is shown
    as-is to surface what the public portal already exposes. Falls back to the
    org-chain tail only when defproc gives no name at all.
    """
    return (tia_name or "").strip() or org_tail(org_chain)


def synth_tender_id(row: dict) -> str:
    """Stable, unique id for listing-only (un-enriched) records."""
    ref = re.sub(r"[^A-Za-z0-9]+", "-", (row.get("ref_no") or "")).strip("-")[:24]
    h = hashlib.md5((row.get("title", "") + "|" + (row.get("ref_no") or "")).encode("utf-8")).hexdigest()[:6]
    return f"LIST_{ref or 'NA'}_{h}"


def _base_record(row: dict) -> dict:
    """Listing-level record (used as-is on degradation)."""
    org_chain = row.get("org_chain", "")
    return {
        "tender_id": synth_tender_id(row),
        "title": row.get("title", ""),
        "org_chain": org_chain,                  # from the org listing (col5 / tree name)
        "location": "",
        "unit": derive_unit("", org_chain),      # org-chain tail as the buyer unit
        "buyer_address": "",
        "pincode": "",
        "value_inr": None,
        "tender_type": "",
        "category": "",
        "description": row.get("title", ""),
        "ref_no": row.get("ref_no", ""),
        "closing_date": row.get("closing_date", ""),
        "closing_iso": row["closing_dt"].strftime("%Y-%m-%d") if row.get("closing_dt") else "",
        "published": _published_iso(row),
        "detail_url": row.get("detail_url", ""),  # session-scoped fetch URL (not stored publicly)
        "enriched": False,
    }


def enrich_record(fetcher, row: dict) -> dict:
    """Follow detail_url and fill the buyer block; degrade gracefully on failure."""
    rec = _base_record(row)
    url = row.get("detail_url", "")
    if not url:
        return rec
    try:
        html = fetcher.get(url).text
    except (ForbiddenEndpoint, GatedContent) as e:
        log.info("gated/forbidden detail, keeping listing record: %s", e)
        return rec
    except Exception as e:  # network/HTTP — fail soft, never crash the run
        log.warning("detail fetch failed (%s), keeping listing record: %s", url[:60], e)
        return rec

    d = P.parse_detail(html)
    if not d:  # gated / no canonical tender id -> degrade
        log.info("detail page not parseable (gated/empty), keeping listing record")
        return rec

    location = d.get("location") or _location_from_address(d.get("buyer_address", ""))
    rec.update({
        "tender_id": d.get("tender_id") or rec["tender_id"],
        "title": d.get("title") or rec["title"],
        "org_chain": d.get("org_chain", ""),
        "location": location,
        "unit": derive_unit(d.get("tia_name", ""), d.get("org_chain", "")),
        "buyer_address": d.get("buyer_address", ""),
        "pincode": d.get("pincode", ""),
        "value_inr": d.get("value_inr"),
        "tender_type": d.get("tender_type", ""),
        "category": d.get("category", ""),
        "description": d.get("description") or rec["description"],
        "enriched": True,
    })
    return rec


def _location_from_address(addr: str) -> str:
    """Best-effort city/district from the buyer address tail (before state)."""
    if not addr:
        return ""
    # address like 'GE Dinjan No 2, Post Dinjan, Dist Tinsukia Assam'
    m = re.search(r"Dist\.?\s+([A-Za-z][A-Za-z .]+?)(?:\s+[A-Z][a-z]+)?$", addr)
    if m:
        return m.group(1).strip()
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    return parts[-1] if parts else ""
