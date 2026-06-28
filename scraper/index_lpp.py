"""Build the prebuilt, static LPP archive index served to the dashboard's LPP
Finder (web/lpp-index.json). Records carry the DPM 2025 §5.35.1 "Database on
Costs & Prices" fields and map to the DPMF 5 Ser 7 / Ser 6(a) / DPMF 7 export.

This is a committed, client-searchable corpus (records + precomputed search
text). It is a drop-in for the dashboard's archive array — the dashboard's
existing client-side search/export consume it unchanged. (We deliberately keep
the dashboard self-contained — no external search library, no outbound calls;
for a ~15k-bid corpus client-side filtering is instant. The field name
`lpp-index.json` matches the design's MiniSearch index slot.)

The export is a DRAFTING AID only (DPMF 5 Note b): escalation/ERV are left as
placeholders for the indenter/IFA — never presented as a vetted SoC.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "web", "lpp-index.json")

# Fields the dashboard LPP card/search/export read (+ §5.35.1 audit fields).
LPP_FIELDS = ("id", "title", "unit", "location", "mode", "date", "qty",
              "value", "l1", "crit", "domains", "named", "ref", "detail_url",
              "category", "no_bidders", "source", "est_value")


# --------------------------------------------------------------------------- #
# DPM financial-year / vintage helpers (mirror the dashboard; §5.33.4(a))
# --------------------------------------------------------------------------- #
def _fy_start(iso: str) -> int | None:
    try:
        d = datetime.fromisoformat(iso[:10])
    except (ValueError, TypeError):
        return None
    return d.year if d.month >= 4 else d.year - 1  # FY starts April


def lpp_fy(iso: str) -> str:
    s = _fy_start(iso)
    return f"{s}-{str((s + 1) % 100).zfill(2)}" if s is not None else ""


def lpp_vintage(iso: str, now: datetime | None = None) -> int | None:
    s = _fy_start(iso)
    if s is None:
        return None
    now = now or datetime.now(timezone.utc)
    now_fy = now.year if now.month >= 4 else now.year - 1
    return now_fy - s


# --------------------------------------------------------------------------- #
# record mapping
# --------------------------------------------------------------------------- #
def _org_tail(org_chain: str) -> str:
    parts = [p.strip() for p in (org_chain or "").split("▸") if p.strip()]
    return parts[-1] if parts else ""


def to_lpp_record(rec: dict) -> dict:
    """Pipeline/archive record -> LPP archive record (DPM §5.35.1)."""
    iso = rec.get("closing_iso") or (rec.get("first_seen", "")[:10])
    unit = rec.get("unit") or _org_tail(rec.get("org_chain", ""))
    out = {
        "id": rec.get("tender_id", ""),
        "title": rec.get("title", ""),
        "unit": unit,
        "location": rec.get("location", ""),
        "mode": rec.get("tender_type") or "Open Tender",   # §5.35.1 mode of tendering
        "date": iso,
        "qty": rec.get("qty") or "as per tender",          # §5.35.1 quantity (partial)
        # SAFEGUARD: the LPP 'value' is ONLY ever the awarded/contracted rate from a
        # closed tender's AoC page. The estimated tender value (a buyer's notional
        # pre-tender figure) must NEVER be presented as an LPP — it lives in
        # 'est_value', clearly separate, and the dashboard never renders it as price.
        "value": rec.get("awarded_value"),
        "l1": rec.get("l1"),
        "crit": rec.get("criticality", "routine"),
        "domains": rec.get("domains", []),
        "named": rec.get("named_system"),
        "ref": rec.get("ref_no", ""),                      # buyer reference (search key)
        "detail_url": rec.get("detail_url", ""),
        # §5.35.1 audit extras
        "category": rec.get("category") or rec.get("product_category", ""),
        "no_bidders": rec.get("no_bidders"),
        "source": f"{unit}, {rec.get('location', '')}".strip(", "),
        "est_value": rec.get("value_inr"),                 # estimated tender value (NOT the LPP)
    }
    # precomputed lowercase search blob (prebuilt index)
    out["_search"] = " ".join(str(x) for x in (
        out["title"], " ".join(out["domains"]), out["named"] or "", out["unit"], out["location"]
    )).lower()
    return out


def build_index(records, out_path: str = DEFAULT_OUT, now: datetime | None = None) -> dict:
    """Dedupe by id, sort newest-first, write the static index. Returns the doc."""
    now = now or datetime.now(timezone.utc)
    by_id: dict[str, dict] = {}
    for r in records:
        lr = to_lpp_record(r)
        if lr["id"]:
            by_id[lr["id"]] = lr
    recs = sorted(by_id.values(), key=lambda r: r.get("date", ""), reverse=True)
    doc = {
        "built": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(recs),
        "fields": list(LPP_FIELDS),
        "records": recs,
    }
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return doc


# --------------------------------------------------------------------------- #
# DPMF 5 / DPMF 7 export (Python port of the dashboard's export — for tests and
# for a CLI drafting aid). Indicative only; escalation/ERV left for the indenter.
# --------------------------------------------------------------------------- #
def _money(v) -> str:
    return "NOT PUBLISHED on defproc — to be obtained from the buying unit" if v in (None, "") \
        else f"₹{v / 1e5:,.2f} lakh"


def soc_export_block(rec: dict, now: datetime | None = None) -> str:
    """DPMF 5 Ser 7 / Ser 6(a) + DPMF 7 + §5.33.4 caveats. rec = LPP record."""
    now = now or datetime.now(timezone.utc)
    iso = rec.get("date", "")
    vint = lpp_vintage(iso, now)
    try:
        dnice = datetime.fromisoformat(iso[:10]).strftime("%d %b %Y")
    except (ValueError, TypeError):
        dnice = iso
    lpp_line = (f"{_money(rec.get('value'))} (per unit basis = total ÷ qty)"
                if rec.get("value") not in (None, "") else _money(rec.get("value")))
    vint_txt = (f"EXCEEDS 3 yrs: not a clean scale; escalate before use (§5.33.4(a))."
                if (vint or 0) > 3 else "within 3 yrs.")
    return (
        "DETAILS OF THE LAST PURCHASE  (per DPM 2025, DPMF 5 — Statement of Case, Ser 7)\n"
        f"(a) Similar item procured: {rec.get('title', '')}\n"
        f"    Quantity & date: {rec.get('qty', '')} on {dnice}\n"
        "(b) Recurring item: to be confirmed by indenter\n"
        f"(c) Mode of tendering (last purchase): {rec.get('mode', '')}\n"
        f"(d) Source of last purchase: {rec.get('source', '')}\n"
        f"(e) Other: tender ref {rec.get('id', '')}; defproc: {rec.get('detail_url', '')}\n\n"
        "ESTIMATED COST — LPP BASIS  (DPMF 5 Ser 6(a) / DPMF 7)\n"
        f"    Last Purchase Price: {lpp_line}\n"
        f"    Price Level / FY of LPP: FY {lpp_fy(iso)}\n"
        f"    Source: {rec.get('source', '')}\n"
        f"    Quantity (LPP order): {rec.get('qty', '')}\n"
        "    Escalation factor: __________  (to be worked out per DPM §5.32.2(c)/(d))\n"
        "    ERV (if import content): __________  (DPM §5.32.2(i))\n\n"
        "PRICE-REASONABLENESS CAVEATS  (DPM §5.33.4)\n"
        f"    - Vintage: LPP is {vint} FY old — {vint_txt}\n"
        "    - Confirm same magnitude & scope of supply (§5.33.4(b)).\n"
        "    - Account for basket price / bulk discount (§5.33.4(c)).\n"
        "    - Consider Price-Variation-Clause final cost paid (§5.33.4(d)).\n"
        "    - Confirm current production vs ex-stock supply (§5.33.4(e)).\n\n"
        "NOTE: Indicative aid drawn from public defproc data. Format is indicative "
        "(DPMF 5, Note b). Escalation/ERV to be completed and the case vetted by the "
        "indenter / IFA per DPM 2025."
    )


# --------------------------------------------------------------------------- #
# CLI: build the committed LPP index (cron-runnable)
# --------------------------------------------------------------------------- #
def _load_tenders(path: str) -> list:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
    return []


def main() -> None:
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Build the LPP archive index (web/lpp-index.json)")
    ap.add_argument("--tenders", default=os.path.join(ROOT, "web", "tenders.json"),
                    help="current tenders to seed the corpus (active bids)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--archive", action="store_true",
                    help="harvest the active by-organisation catalogue (network)")
    ap.add_argument("--max-orgs", type=int, default=None, help="cap number of orgs (default: all)")
    ap.add_argument("--per-org-cap", type=int, default=None, help="cap tenders per org (default: all)")
    ap.add_argument("--enrich-match", default=r"printer|otdr|\bamc\b|annual maint|hiring|comput|"
                    r"photocop|toner|laptop|\bups\b|networking|software|repair of",
                    help="regex: enrich (detail page) records whose title matches")
    ap.add_argument("--enrich-cap", type=int, default=40)
    ap.add_argument("--min-delay", type=float, default=3.0)
    args = ap.parse_args()

    records = list(_load_tenders(args.tenders))
    if args.archive:
        from .archive import scrape_corpus
        from .fetch import Fetcher
        f = Fetcher(min_delay=args.min_delay)
        records += scrape_corpus(f, max_orgs=args.max_orgs, per_org_cap=args.per_org_cap,
                                 enrich_match=args.enrich_match, enrich_cap=args.enrich_cap)
    doc = build_index(records, args.out)
    crit = sum(r["crit"] == "critical" for r in doc["records"])
    print(f"lpp-index.json: {doc['count']} records ({crit} critical) -> {args.out}")


if __name__ == "__main__":
    main()
