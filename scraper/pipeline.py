"""Live pipeline: fetch -> parse -> enrich -> classify -> geocode -> diff/retain
-> write data/tenders.json (the dashboard's input).

Run:  python -m scraper.pipeline --out data/tenders.json
Only this code (in GitHub Actions) reaches defproc.gov.in; the dashboard never does.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from . import parse as P
from .classify_map import classify_record
from .diff import merge_and_retain
from .enrich import enrich_record
from .fetch import BASE, ENTRY_POINTS, TENDER_LOOKUP_URL, Fetcher
from .geocode import geocode_record, save_cache as _save_geocache

log = logging.getLogger("defproc.pipeline")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Served beside the dashboard (its CONFIG.DATA_URL = "./tenders.json"); web/ is
# the static publish dir. data/ holds offline build inputs (pincodes, archive).
DEFAULT_OUT = os.path.join(ROOT, "web", "tenders.json")
_IST = timedelta(hours=5, minutes=30)

# Dashboard data-contract fields (live view reads exactly these + a few extras).
# 'published' (e-Published date, UTC ISO) drives novelty + the 72h window; the
# dashboard falls back to first_seen when a record predates this field.
CONTRACT_FIELDS = ("tender_id", "title", "org_chain", "location", "unit",
                   "buyer_address", "pincode", "lat", "lng", "criticality",
                   "confidence", "domains", "named_system", "closing_date",
                   "published", "first_seen")


def assemble_record(base: dict) -> dict:
    """Listing+detail base -> full record (classify + geocode), pre-diff."""
    cls = classify_record(base.get("title", ""), base.get("description", ""))
    lat, lng = geocode_record(base)
    return {
        "tender_id": base["tender_id"],
        "title": base.get("title", ""),
        "org_chain": base.get("org_chain", ""),
        "location": base.get("location", ""),
        "unit": base.get("unit", ""),
        "buyer_address": base.get("buyer_address", ""),
        "pincode": base.get("pincode", ""),
        "lat": lat,
        "lng": lng,
        "criticality": cls["criticality"],
        "confidence": cls["confidence"],
        "domains": cls["domains"],
        "named_system": cls["named_system"],
        "closing_date": base.get("closing_date", ""),
        "published": base.get("published", ""),
        # stable, durable public link (session $DirectLink would die for viewers)
        "detail_url": TENDER_LOOKUP_URL,
        # extras (handy on the card / for audit; dashboard ignores unknowns)
        "value_inr": base.get("value_inr"),
        "tender_type": base.get("tender_type", ""),
        "category": base.get("category", ""),
        "ref_no": base.get("ref_no", ""),
        "status": "active",
    }


def collect_recent_rows(fetcher: Fetcher, retention_hours: int, now: datetime) -> list[dict]:
    """All active tenders across the by-organisation tree whose e-Published date
    is within the retention window (the 'newly published' set). Comprehensive —
    not just the Home top-10."""
    cutoff = now - timedelta(hours=retention_hours)
    try:
        tree = fetcher.get(BASE + ENTRY_POINTS["by_organisation"]).text
    except Exception as e:  # noqa: BLE001
        log.warning("org tree failed: %s", e)
        return []
    orgs = P.find_org_count_links(tree)
    log.info("org tree: %d orgs, %d active advertised", len(orgs), sum(o["count"] for o in orgs))
    rows: list[dict] = []
    seen: set[str] = set()
    for o in orgs:
        try:
            html = fetcher.get(o["url"]).text
        except Exception as e:  # noqa: BLE001 — one org must not abort the run
            log.warning("org list (count=%s) failed: %s", o["count"], e)
            continue
        for r in P.parse_org_listing(html):
            pdt = r.get("published_dt")
            if pdt is None:
                continue
            p_utc = (pdt - _IST).replace(tzinfo=timezone.utc)
            if p_utc < cutoff:
                continue  # older than the window
            if r["detail_url"] in seen:
                continue
            if not r.get("org_chain"):
                r["org_chain"] = o.get("name", "")  # seed from the org tree
            seen.add(r["detail_url"])
            rows.append(r)
    rows.sort(key=lambda r: r.get("published_dt") or datetime.min, reverse=True)
    return rows


def run_live(fetcher: Fetcher, out_path: str = DEFAULT_OUT, retention_hours: int = 72,
             max_enrich: int | None = None, now: datetime | None = None,
             verify_cap: int = 100) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    rows = collect_recent_rows(fetcher, retention_hours, now)
    log.info("tenders published within %dh: %d", retention_hours, len(rows))
    records = []
    enriched = 0
    verified = 0
    for i, row in enumerate(rows):
        do_enrich = max_enrich is None or i < max_enrich  # enrich -> classify on title+desc
        base = enrich_record(fetcher, row) if do_enrich else _listing_only(row)
        enriched += int(bool(base.get("enriched")))
        rec = assemble_record(base)
        # Layer 2 — verify-before-flag: a CRITICAL verdict from an un-enriched
        # title gets its (session-open, non-captcha) detail page fetched and is
        # re-classified on title + work-description through the same gate.
        if rec["criticality"] == "critical" and not base.get("enriched") and verified < verify_cap:
            base2 = enrich_record(fetcher, row)
            verified += 1
            if base2.get("enriched"):
                rec = assemble_record(base2)
                enriched += 1
        records.append(rec)
    if verified:
        log.info("verify-before-flag: enriched %d title-critical records", verified)

    existing = _load(out_path)
    merged = merge_and_retain(records, existing, now=now, retention_hours=retention_hours)
    _write(out_path, merged)
    _save_geocache()  # persist online-geocode cache (committed; cheap repeat runs)
    log.info("wrote %d records -> %s (enriched %d/%d, requests %d)",
             len(merged), out_path, enriched, len(rows), fetcher.count)
    return merged


def _listing_only(row: dict) -> dict:
    from .enrich import _base_record
    return _base_record(row)


def _load(path: str) -> list[dict]:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _write(path: str, records: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="defproc-monitor live pipeline")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--retention-hours", type=int, default=72,
                    help="show tenders published within this window")
    ap.add_argument("--max-enrich", type=int, default=None,
                    help="cap detail-page fetches (enrich -> classify on title+description)")
    ap.add_argument("--verify-cap", type=int, default=100,
                    help="max extra detail fetches to verify title-critical verdicts")
    ap.add_argument("--min-delay", type=float, default=3.0)
    args = ap.parse_args()
    fetcher = Fetcher(min_delay=args.min_delay)
    recs = run_live(fetcher, args.out, args.retention_hours, args.max_enrich,
                    verify_cap=args.verify_cap)
    crit = sum(r["criticality"] == "critical" for r in recs)
    print(f"tenders.json: {len(recs)} records, {crit} critical, {fetcher.count} requests")


if __name__ == "__main__":
    main()
