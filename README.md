# defproc-monitor

> **Disclaimer:** Independent, non-commercial, informational project — **not affiliated
> with, endorsed by, or connected to** MoD, the Government of India, NIC, GePNIC, or
> defproc.gov.in. All data is aggregated from **publicly accessible** pages of
> defproc.gov.in and reproduced **"as is"**; it may be inaccurate, incomplete, outdated,
> or auto-misclassified, and is **not an official record** — verify against defproc.gov.in.
> Provided with **no warranty and no liability** to the maximum extent permitted by law.
> See [`DISCLAIMER.md`](DISCLAIMER.md). Licensed under **Apache-2.0** (see [`LICENSE`](LICENSE)).

A **free, single-source tender monitor** for [`defproc.gov.in`](https://defproc.gov.in)
(NIC GePNIC, MoD eProcurement). It scrapes public tender listings, tags + geocodes
them, and serves a static public dashboard with two views:

- **Live Monitor** — stream of tenders **published in the last 72 h** + the official
  sovereign map of India + buyer-address flash card, CRITICAL items highlighted.
- **LPP Finder** — searches the active defproc catalogue for the **item + buyer + tender
  reference**, mapped to **DPM 2025** forms (DPMF 5 Ser 7 / Ser 6(a) / DPMF 7) with §5.33.4
  vintage caveats. Awarded prices are captcha-gated on defproc, so this is a reference +
  drafting-skeleton tool, not a price database (the LPP is obtained from the buying unit).

Everything runs at **₹0**: GitHub Actions (cron compute) → committed JSON → static host.
Only the scraper (in Actions) ever reaches defproc; the deployed dashboard is static,
public, and makes **no outbound calls**.

## Live-site reality (verified 2026-06-28)

GePNIC gates its *interactive* flows behind a CAPTCHA and leaves the *published* listings
open — so we crawl only the open paths and **never** touch the gated ones:

| Path | Status (verified live) | Used? |
|---|---|---|
| **by-organisation** drill-down (`S.No · e-Published · Closing · Opening · Title+Ref · Org`) | open, CAPTCHA-free | ✅ **primary feed + corpus** |
| `?page=Home` latest-tenders widget | open, CAPTCHA-free (only the latest ~10) | ◑ supplementary |
| per-tender detail page (`td_caption`/`td_field` + Tender Inviting Authority block) | open | ✅ enrichment |
| **by-location / by-date** | **selection form / gated** (not a plain GET) | 🚫 not used |
| **Tenders-in-Archive · Results-of-Tenders (AoC) · Tender-Status · Cancelled** | **CAPTCHA-gated** (POST + `captchaText`) | 🚫 deny-listed |
| MIS Reports portal (`gepnicreports.gov.in`) | CAPTCHA-gated (and a 2nd source) | 🚫 not used |
| `FrontEndLatestActiveTenders` / `FrontEndAdvancedSearch` (keyword **Search**), login, doc-download | **CAPTCHA-gated** | 🚫 deny-listed |

> **Consequence (load-bearing):** awarded prices live only in the **closed/awarded**
> pages (Archive + Results/AoC), which are **all CAPTCHA-gated**. defproc publishes data
> for free while a tender is *active* (no LPP yet) and gates it once it's *awarded* (has an
> LPP). So a free, ethical **LPP price database is not achievable** — the LPP Finder is a
> *reference + drafting-skeleton* tool (see below), not a price source. There is also **no
> stable per-tender URL** (every detail link is session-scoped), so the public "look up on
> defproc" link is human-in-the-loop: it opens the Tender-Status page and the viewer pastes
> the Tender ID + solves the one captcha.

`robots.txt` returns 404 (nothing disallowed); we are polite regardless — UA
`defproc-monitor/0.1`, ≥ 3 s between requests, one worker. There is no RSS/Atom feed and
no bulk export on this instance, so HTML scraping of the open pages is the route.

These limits are **enforced** (not just documented) by `scraper/fetch.py`'s URL deny-list
and the `tests/test_ethics_gates.py` CI gate.

## Architecture

```
GitHub Actions (cron, twice daily)
  └─ scraper/  fetch → parse → enrich → classify → geocode → diff/retain
                                                  → archive → index_lpp
       → web/tenders.json + web/lpp-index.json  (committed)
       → static host redeploys → dashboard reads the JSON client-side
```

## Layout

```
scraper/
  fetch.py        polite public GETs; deny-list for gated/Search/login/download
  parse.py        all GePNIC HTML parsing (listing table + detail td_caption/field)
  enrich.py       detail-page buyer block; personnel-name guard; graceful degrade
  classify.py     SUPPLIED + FINAL ProcurementClassifier (stdlib only) — used as-is
  classify_map.py thin adapter: classify.py result → criticality/domains/named_system
  geocode.py      lat/lng — OSM Nominatim (free, cached) + offline gazetteer fallback
  diff.py         idempotent diff vs previous + 72h(+buffer) retention
  archive.py      scrape Tenders-in-Archive + Results/AoC + by-* drill-downs (bounded)
  index_lpp.py    build web/lpp-index.json (DPM §5.35.1 records) + DPMF 5/7 export
  pipeline.py     orchestrator → web/tenders.json
web/
  defproc-tender-watch.html   the dashboard (supplied; only CONFIG wired)
  india-official.geojson      sovereign boundary (supplied; embedded in the dashboard)
  index.html                  redirect → the dashboard
  tenders.json / lpp-index.json   committed data (produced by the scraper)
data/
  pincodes.csv    offline geocode table (curated India-Post subset)
  archive/        reserved for the growing raw corpus
tests/            per-phase gates + boundary + ethics gates (run in CI)
```

## Run locally

```bash
pip install -r requirements.txt

# Live monitor data → web/tenders.json
python -m scraper.pipeline --out web/tenders.json --entries home

# LPP archive index → web/lpp-index.json (--archive also crawls Archive/Results/by-*)
python -m scraper.index_lpp --archive --max-rows 60 --max-enrich 20

# Preview the dashboard (serve web/ so ./tenders.json + ./lpp-index.json resolve)
python -m http.server -d web 8000      # → http://localhost:8000/
```

## Test

```bash
python -m pytest -q          # all phase gates, boundary, ethics gates (offline)
python tests/test_boundary.py   # sovereign-map point-in-polygon, standalone
```

CI (`.github/workflows/ci.yml`) runs the suite on every push. The cron
(`.github/workflows/scrape.yml`) scrapes twice daily and commits the data.

## Deploy the public dashboard (free)

The site is `web/` (static). Connect the repo once; every commit the Action makes
redeploys automatically.

**Netlify**
```bash
npm i -g netlify-cli
netlify deploy --dir web --prod      # or: New site from Git (publish dir = web/)
```
`netlify.toml` already sets `publish = "web"` and maps `/` → the dashboard.

**Vercel**
```bash
npm i -g vercel
vercel --prod                        # set Project → Settings → Root Directory = web
```
`vercel.json` provides `cleanUrls` + the `/` rewrite. (GitHub Pages also works:
Settings → Pages → deploy `/web`.)

No API keys, no secrets, no backend — the deployed page only fetches its own
same-origin `tenders.json` / `lpp-index.json`.

## Data contract (`web/tenders.json`)

Array of records the dashboard reads directly:
`tender_id, title, org_chain, location, unit, buyer_address, pincode, lat, lng,
criticality ("critical"|"routine"), confidence, domains[], named_system,
closing_date, published (UTC ISO), first_seen (ISO 8601)`.
`criticality/domains/named_system/confidence` come from `scraper/classify.py`
(classified on **title + work-description** once the detail page is enriched).

**Novelty + retention key off `published`** (defproc's e-Published date, IST→UTC) —
**not** our discovery time — so a tender published a month ago never shows as "new". The
Live Monitor is a **"published in the last 72 h"** feed (stream + map drain together at
72 h; the served file keeps a small buffer). The bid **closing date** is shown separately
on each card. `detail_url` is the **stable Tender-Status lookup page** (session links die);
the canonical `tender_id` is shown for the viewer to paste + solve the captcha.

## Scope & ethics (hard rules)

Public defproc endpoints only; never the Search form, login, or document download;
never CAPTCHA solving/OCR/replay — gated content is logged and degraded, never
bypassed. Single source (defproc.gov.in). **Not built:** ORBAT/unit-hierarchy,
dark-unit inference, personnel/LinkedIn correlation, satellite/installation
geolocation. The dashboard displays only what the tender itself publishes.

The map is rendered from the supplied **datameet Survey-of-India-aligned** boundary
(Aksai Chin, PoK, Gilgit-Baltistan, Shaksgam, full Arunachal incl. Tawang) with **no
tile basemap**; `tests/test_boundary.py` enforces sovereign coverage in CI.

## LPP Finder (DPM 2025) — reference + drafting aid, **not a price database**

Awarded prices are CAPTCHA-gated on defproc (see the reality table), so the LPP Finder
searches the **freely-accessible active catalogue** to locate the **item + buyer + tender
reference**, then exports a DPMF 5 Ser 7 / Ser 6(a) / DPMF 7 "Details of the Last Purchase"
block (with §5.33.4 vintage caveats and §5.32.2 escalation/ERV **placeholders left for the
indenter/IFA**). The actual LPP must be **obtained from the buying unit** (or read manually
off the captcha-gated Award-of-Contract page). **Safeguard:** a record's LPP `value` is only
ever an *awarded* contract value — a buyer's notional `est_value` is kept separate and
**never** rendered as a price (`tests/test_lpp_index.py::test_est_value_never_becomes_lpp`).
It is a drafting aid, never a vetted Statement of Case.

## Geocoding (accurate, free, scraper-side)

`scraper/geocode.py` triangulates coordinates from every field defproc gives us. With
`DEFPROC_GEOCODE_ONLINE=1` (set in the cron) it queries **OpenStreetMap Nominatim** (free,
no key) — full address → pincode → city — and **caches** results in `data/geocache.json`
(committed, so we never re-query and stay within 1 req/s). It falls back to an offline
gazetteer + India-Post pincode CSV + PIN-prefix centroid for the cryptic military addresses
Nominatim can't resolve. This runs **only in the scraper** (GitHub Actions); the deployed
dashboard still makes zero outbound calls.

## Limits

- The Live Monitor covers the **whole active by-organisation catalogue** filtered to the
  72 h publish window (comprehensive, not just the Home top-10). Per-tender enrichment is
  bounded per run and continues across cron ticks.
- **Per-tender linking (verified):** defproc's `$DirectLink` *is* a stable per-tender reference
  (its encrypted `sp` blob resolves the same tender in any session), **but** it needs a live
  JSESSIONID cookie — a cold click hits a "Stale Session" page. The `service=page` Tender-Status
  **search** page, by contrast, renders cold. So every card in **both** views links there and
  **auto-copies** the canonical Tender ID (or the buyer reference for un-enriched rows) and toasts
  "paste it + solve the captcha" — guided, not stranded. `detail_url` = that search page.
- Awarded LPP prices and the historical archive are CAPTCHA-gated and therefore out of reach
  for an automated free crawl — by design we stop at the wall.
- Portal HTML changes will break parsers periodically — all parsing is isolated in
  `scraper/parse.py` so fixes are one-file.
