"""Build a large LPP archive corpus from defproc's public **by-organisation**
drill-down (CAPTCHA-free): the org tree exposes each organisation's full tender
list (title, ref, e-published/closing dates, org chain, detail link) — typically
several thousand active tenders across the portal, all via plain GETs.

Two tiers (politeness: enriching every tender at ≥3 s is hours, so we don't):
  * catalogue tier — every harvested tender, classified on its title. Makes the
    LPP search cover ~the whole active catalogue. Value/buyer = "obtain from unit"
    until enriched (DPM §5.35.1-correct).
  * enriched tier — a bounded subset (e.g. records matching a search) gets the
    detail page → estimated value, mode, buyer block, pincode.

The historical **Tenders-in-Archive** + **Results/AoC** sit behind a selection
form (org/date dropdown), not a plain GET — crawling them (for awarded values) is
the documented next step, gated on confirming the form is GET-and-not-CAPTCHA.
"""
from __future__ import annotations

import logging
import re

from . import parse as P
from .classify_map import classify_record
from .enrich import _published_iso, derive_unit, enrich_record, synth_tender_id
from .fetch import BASE, ENTRY_POINTS, TENDER_LOOKUP_URL, Fetcher

log = logging.getLogger("defproc.archive")

_ENRICH_FIELDS = ("tender_id", "org_chain", "location", "unit", "buyer_address",
                  "pincode", "value_inr", "tender_type", "category")


def harvest_active(fetcher: Fetcher, max_orgs: int | None = None,
                   per_org_cap: int | None = None) -> list[dict]:
    """Org tree -> each org's tender list -> deduped rich listing rows."""
    tree = fetcher.get(BASE + ENTRY_POINTS["by_organisation"]).text
    orgs = P.find_org_count_links(tree)
    orgs.sort(key=lambda o: -o["count"])
    total = sum(o["count"] for o in orgs)
    log.info("org tree: %d orgs, %d active tenders advertised", len(orgs), total)
    if max_orgs:
        orgs = orgs[:max_orgs]
    rows: list[dict] = []
    seen: set[str] = set()
    for o in orgs:
        try:
            html = fetcher.get(o["url"]).text
        except Exception as e:  # noqa: BLE001 — one org must not abort the harvest
            log.warning("org list (count=%s) failed: %s", o["count"], e)
            continue
        got = 0
        for r in P.parse_org_listing(html):
            if r["detail_url"] in seen:
                continue
            if not r.get("org_chain"):
                r["org_chain"] = o.get("name", "")  # seed from the org tree
            seen.add(r["detail_url"])
            rows.append(r)
            got += 1
            if per_org_cap and got >= per_org_cap:
                log.info("org (advertised %d) capped at %d rows", o["count"], per_org_cap)
                break
    log.info("harvested %d unique tenders from %d orgs", len(rows), len(orgs))
    return rows


def row_to_record(row: dict) -> dict:
    """Listing row -> classified corpus record (catalogue tier, un-enriched)."""
    cls = classify_record(row.get("title", ""))
    closing_iso = row["closing_dt"].strftime("%Y-%m-%d") if row.get("closing_dt") else ""
    if not closing_iso and row.get("published_date"):
        pdt = P.parse_gepnic_datetime(row["published_date"])
        closing_iso = pdt.strftime("%Y-%m-%d") if pdt else ""
    org_chain = row.get("org_chain", "")
    return {
        "tender_id": synth_tender_id(row),
        "title": row.get("title", ""),
        "org_chain": org_chain,
        "location": "",
        "unit": derive_unit("", org_chain),
        "buyer_address": "",
        "pincode": "",
        "tender_type": "",
        "value_inr": None,
        "awarded_value": None,
        "l1": None,
        "closing_iso": closing_iso,
        "closing_date": row.get("closing_date", ""),
        "published": _published_iso(row),
        "criticality": cls["criticality"],
        "confidence": cls["confidence"],
        "domains": cls["domains"],
        "named_system": cls["named_system"],
        "detail_url": TENDER_LOOKUP_URL,  # stable public link (session links die)
        "ref_no": row.get("ref_no", ""),
        "enriched": False,
    }


def scrape_corpus(fetcher: Fetcher, max_orgs: int | None = None,
                  per_org_cap: int | None = None, enrich_match: str | None = None,
                  enrich_cap: int = 40) -> list[dict]:
    """Harvest the catalogue, classify, and enrich a bounded matched subset."""
    rows = harvest_active(fetcher, max_orgs, per_org_cap)
    records = [row_to_record(r) for r in rows]

    if enrich_match:
        pat = re.compile(enrich_match, re.I)
        done = 0
        for rec, row in zip(records, rows):
            if done >= enrich_cap:
                break
            if not pat.search(rec["title"]):
                continue
            e = enrich_record(fetcher, row)
            if not e.get("enriched"):
                continue
            for k in _ENRICH_FIELDS:
                if e.get(k) not in (None, ""):
                    rec[k] = e[k]
            cls = classify_record(rec["title"], e.get("description", ""))
            rec.update(criticality=cls["criticality"], confidence=cls["confidence"],
                       domains=cls["domains"], named_system=cls["named_system"])
            rec["enriched"] = True
            done += 1
        log.info("enriched %d records matching %r", done, enrich_match)
    return records
