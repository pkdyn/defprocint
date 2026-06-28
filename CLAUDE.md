# CLAUDE.md — defproc-monitor

Standing context and rules for this project. Read this fully before writing code.
The full design lives in `defproc-monitor-design.md`; this file is the operational contract.

## What this is
A **free, single-source tender monitor** for `defproc.gov.in` (NIC GePNIC, MoD eProcurement).
It scrapes public tender listings, tags + geocodes them, and serves a static public dashboard with
two views: a **Live Monitor** (stream + official India map + buyer-address flash card, 72-hour
retention) and an **Archive / LPP Finder** (search past + current bids for Last Purchase Price
discovery, mapped to DPM 2025 — see `DPM_LPP_MAPPING.md`).
The dashboard is **already built** at `web/defproc-tender-watch.html` — wire it, do not rebuild it.

## Hard rules — scraping ethics (do not violate)
1. **Public endpoints only.** Crawl the GePNIC listing pages, the per-tender detail pages linked
   from them, and the **Tenders-in-Archive** and **Results/Award-of-Contract** pages (for the LPP
   archive). Browse **by organisation / by location / by date**. These are open GET URLs (search
   engines index them).
2. **Never automate the Search form, login, or document-download** flows — those are the
   CAPTCHA-gated paths.
3. **Never implement CAPTCHA solving**, OCR-defeat, token replay, or paid solver integration
   against defproc. If content needs a challenge solved or a login, STOP, log it, and degrade
   gracefully (keep the listing-level record, skip the gated field). Do not bypass.
4. **Polite crawler:** real descriptive User-Agent, ≥ 3 s between requests, one worker, one
   pass per cron tick, honour `robots.txt`.
5. **Prefer official channels first:** check for an RSS/Atom feed and for bulk data on
   data.gov.in before relying on HTML scraping.

## Hard rules — scope (do not build)
This is a tender monitor. It displays only what the tender itself publishes. Do **not** build,
and do not add code paths toward:
- ORBAT / order-of-battle or unit-hierarchy generation
- "dark unit" / unlisted-unit inference
- personnel name/rank extraction or LinkedIn / social correlation
- satellite or precise installation geolocation
- any source other than defproc.gov.in (no GeM, CPPP, aggregators)

## Classification rule
- Use `scraper/classify.py` (`ProcurementClassifier`) to label every tender **critical/routine**.
- Classify on the **item text** — `title`, plus `description` once the detail page is enriched.
- Do **not** feed unit/org as the classification driver: in this classifier unit/org names are
  metadata only and must never flip a verdict (a cleaning contract for DRDO stays ROUTINE).
- CRITICAL drives the map highlight and priority ordering; ROUTINE is shown but muted.

## Hard rules — cost
Everything must run **free**: GitHub Actions (cron compute) + a static host + a committed
JSON file. No paid APIs, no paid proxies, no paid CAPTCHA services, no managed DB.

## Architecture
GitHub Actions (cron) → `scraper/` (fetch → parse → enrich → tag → geocode → diff/retain)
→ commit `data/tenders.json` → static host rebuilds → dashboard reads the JSON client-side.
The deployed dashboard is static and public: no backend, no API keys, no outbound calls. Only the
scraper (in GitHub Actions) reaches defproc.gov.in.

## Working practices
See `@CLAUDE-TIPS.md` for the full playbook. Load-bearing habits: verify before claiming (run the
check, read the real output), deterministic test gates over self-judged "done", surgical diffs, and
encode the hard limits below as CI gates / deny-lists / hooks rather than relying on prose alone.

## Conventions
- Python 3.11+. Libraries: `requests`, `beautifulsoup4`. Keep it minimal.
- `scraper/classify.py` is **supplied and final** (stdlib-only: `re`, `dataclasses`). Use it as-is;
  do not rewrite its keyword sets. Import `ProcurementClassifier` and call `.classify(text)`.
- Keep all HTML-parsing logic isolated in `scraper/parse.py` (the portal changes; fixes
  should be one-file).
- Idempotent runs: diff against existing `data/tenders.json`; never duplicate IDs.
- Fail soft: a broken detail page must not crash the run; log and continue.

## Data contract (scraper output === dashboard input)
`data/tenders.json` is an array of records. The dashboard reads exactly these fields:
```json
{
  "tender_id": "string",
  "title": "string",
  "org_chain": "Ministry of Defence ▸ … ▸ …",
  "location": "Mumbai",
  "unit": "Naval Dockyard (Mumbai)",
  "buyer_address": "Shahid Bhagat Singh Marg, Near Lion Gate, Mumbai",
  "pincode": "400023",
  "lat": 19.076,
  "lng": 72.877,
  "criticality": "critical|routine",
  "confidence": 1.0,
  "domains": ["STRIKE"],
  "named_system": "BrahMos",
  "closing_date": "30 Jun",
  "first_seen": "2026-06-12T06:00:00Z"
}
```
`first_seen` is ISO 8601. If `lat`/`lng` are absent the dashboard falls back to a city table,
but the scraper should fill them. `criticality`/`domains`/`named_system`/`confidence` come from
`scraper/classify.py`. Retain live records with `first_seen` within 72 h (+ small buffer).
The **archive corpus** (active + archive + Results/AoC) is separate, carries the DPM §5.35.1 fields
plus `detail_url` and awarded `value`/`l1` where defproc publishes them, and is served to the LPP
Finder as a prebuilt **MiniSearch** index `data/lpp-index.json` (mid-size ~15k, pure free-static).

## Definition of done (per milestone)
- **M1 fetch+parse:** real `tenders.json` from live `FrontEndLatestActiveTenders`, columns and
  pagination verified against the actual HTML.
- **M2 enrich:** buyer block filled from detail pages; gated pages degrade cleanly.
- **M3 classify+geocode:** wire `classify.py` → `criticality/confidence/domains/named_system`;
  lat/lng filled from offline pincode CSV. Validate against real scraped titles (e.g. a UAV/EW
  tender → CRITICAL; a housekeeping tender → ROUTINE).
- **M4 diff+retain:** idempotent diff and 72 h retention written to `data/tenders.json`.
- **M5 action:** `.github/workflows/scrape.yml` runs on cron and commits data.
- **M6 wire dashboard:** set `CONFIG.DATA_URL="./tenders.json"`; deploy `web/`; swap in the
  vetted `web/india-official.geojson`.

## Testing & verification (hard rule)
Build each phase, then **test and verify it before moving to the next** — no stage is "done" on
code alone. Put tests in `tests/`, wire them into a CI check (GitHub Actions), and keep fixtures of
known inputs/outputs. Minimum bar per phase:
- fetch+parse → real records, schema + uniqueness pass, sample diffed against the live page
- enrich → buyer block filled; gated detail pages degrade without crashing
- classify → `classify.py` self-test passes + a labelled fixture classifies correctly
- geocode → known pincodes/cities resolve within tolerance
- diff+retain → new IDs found, no duplicates, records expire at exactly 72 h
- boundary → `tests/test_boundary.py` point-in-polygon passes (see Map compliance)
- archive+index → archive/AoC scraped, awarded value captured where published, lpp-index.json builds & loads
- LPP Finder → item search returns expected bids, vintage caveat flags LPP>3FY, export = valid DPMF 5 Ser 7/DPMF 7
- dashboard → both views render; live: stream+map, CRITICAL highlighted, flash card + defproc link; LPP: search+results+export
After all phases are individually green, run **one final end-to-end pass** (live scrape → … →
tenders.json → dashboard shows real data with correct criticality and the sovereign map). The build
is done only after that E2E pass.

## LPP Finder rule (DPM 2025)
The archive search is for Last Purchase Price discovery. Map every result to the DPM forms exactly
as set out in `DPM_LPP_MAPPING.md` (verified against DPM Vol I & II): §5.35.1 fields, DPMF 5 Ser 7 /
Ser 6(a) / DPMF 7 export, §5.33.4 caveats, §5.32.2 escalation/ERV. The export is a **drafting aid**
— never present it as a completed/vetted SoC; escalation/ERV are left for the indenter/IFA.

## Map compliance (non-negotiable)
The dashboard renders India from `web/india-official.geojson` — the **datameet/maps Country** file
(official Survey-of-India-aligned land area incl. Aksai Chin, PoK, Gilgit-Baltistan, Shaksgam),
simplified. The renderer handles Polygon **and MultiPolygon** (mainland + islands). **No tile
basemap, ever** — that is the only way no de-facto border leaks in.
Coverage is enforced by `tests/test_boundary.py`: a point-in-polygon check that Aksai Chin,
Gilgit-Baltistan, PoK, Siachen, Shaksgam, **Tawang** and the full Arunachal salient are all INSIDE.
This test must pass in CI. Do not replace the boundary with OSM/Google tiles or a de-facto file.
