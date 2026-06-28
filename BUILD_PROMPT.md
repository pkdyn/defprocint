Build the entire defproc-monitor project now, end to end, in one pass. Do not stop for
confirmation between steps — produce a working system and show me the result at the end.
Read CLAUDE.md, defproc-monitor-design.md, and CLAUDE-TIPS.md first and obey them, and apply
the working practices in CLAUDE-TIPS.md throughout. Build each phase, then
test and verify it before moving to the next — write the test, run it, show it green. Keep tests
in tests/ and wire a CI check. "One pass" means no pausing for my confirmation, not skipping
verification.

Non-negotiable constraints (also in CLAUDE.md):


Public endpoints only. Crawl the GePNIC listing pages and the detail pages linked from
them, browsing by organisation / location / date. Never automate Search, login, or
document-download. Never implement CAPTCHA solving, OCR-defeat, or solver integration —
if something needs a challenge solved or a login, log it and degrade gracefully.
scraper/classify.py is supplied and FINAL. Import ProcurementClassifier and use it
as-is. Do not modify its keyword sets.
Free-only stack: GitHub Actions + a committed JSON file + a static host. No paid APIs,
proxies, CAPTCHA services, or managed DB.
Single source (defproc.gov.in). Forbidden scope: no ORBAT / order-of-battle,
dark-unit inference, personnel or LinkedIn correlation, or satellite/installation
geolocation. Display only what the tender itself publishes.
LPP Finder: map every archive result to DPM 2025 exactly per DPM_LPP_MAPPING.md
(§5.35.1 fields; DPMF 5 Ser 7 / Ser 6(a) / DPMF 7 export; §5.33.4 caveats; §5.32.2 escalation/ERV).
The export is a drafting aid — leave escalation/ERV for the indenter; never present it as a vetted SoC.
Map: web/india-official.geojson is supplied — the datameet Survey-of-India-aligned
official sovereign boundary (Aksai Chin, PoK, Gilgit-Baltistan, Shaksgam, full Arunachal incl.
Tawang). Use it as-is, render with no tile basemap, and keep tests/test_boundary.py
(point-in-polygon for those regions) green. Do not substitute an OSM/Google or de-facto file.


Working practices (apply CLAUDE-TIPS.md throughout — especially):


Verify, don't assert. Every phase needs a runnable pass/fail check (a test, a build exit code,
tests/test_boundary.py, a real archive query). Run it, read the actual output, then call the
phase done — "done" is a claim, not proof (§1, §0a).
Deterministic gates, not self-judgement. Gate progress on actually running the tests and
checking exit codes — never on your own reading of a transcript (§0a, §8).
Read the real thing first. Inspect the live defproc HTML and actual command output before
claiming structure or success — don't state an easy-to-check guess as fact (§11).
Proceed; don't over-ask. This is one-shot: make reasonable assumptions, note them inline, keep
going rather than stopping for confirmation. Restate the top-level goal in your plan so it isn't
lost mid-run (§0a, §10).
Surgical diffs, simplicity first. Smallest change that works; leave the verified live-monitor
code and the sovereign boundary untouched.
Encode hard limits as enforcement, not just prose. Back the non-negotiables (public endpoints
only / no CAPTCHA-bypass / no document-download / forbidden scope / boundary test green) with
deterministic CI gates and deny-lists/hooks where feasible — prose rules are best-effort (§0a, §16).


Build, in order:


Scaffold the repo per the design doc, including a tests/ dir and a .github/workflows/ci.yml
that runs the tests on push. requirements.txt = requests, beautifulsoup4 (classify.py is
stdlib-only). Add a README.md. tests/test_boundary.py is supplied (point-in-polygon over
web/india-official.geojson) — run it and confirm it passes now (it should), then keep it green.
Verify the live site before coding parsers. GET
https://defproc.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page, inspect the
real HTML, and confirm — do not assume — the actual table columns, the row→detail-page link,
and the pagination parameter. Read robots.txt. Check whether defproc exposes an RSS/Atom or
bulk export and prefer it if it exists. Report findings inline, then code to what you found.
scraper/fetch.py (polite GET + pagination; real User-Agent; ≥3s delay; single worker) and
scraper/parse.py (table → records matching the data contract in CLAUDE.md).
scraper/enrich.py — follow detail_url → unit / buyer_address / pincode. Gated pages
degrade cleanly: keep the listing-level record, skip the gated field.
Classification — from classify import ProcurementClassifier. Classify each tender on its
title, then re-run on title + " " + description after enrichment →
criticality / confidence / domains / named_system. Unit/org is metadata only and must never
flip a verdict (housekeeping for a defence lab stays ROUTINE).
scraper/geocode.py — offline India Post pincode CSV → lat / lng.
scraper/diff.py — idempotent diff vs the existing data/tenders.json + 72h retention
(+ small buffer).
.github/workflows/scrape.yml — cron (twice daily): run the pipeline, commit data/tenders.json.
Wire the dashboard: set CONFIG.DATA_URL="./tenders.json" in
web/defproc-tender-watch.html. The boundary web/india-official.geojson is already supplied
and already embedded in the dashboard; if you switch the dashboard to fetch the external file
instead, keep the MultiPolygon renderer and re-run tests/test_boundary.py.
Run the pipeline once locally to produce a real data/tenders.json from live listings,
so the dashboard shows live data.
scraper/archive.py — also scrape Tenders-in-Archive and Results/Award-of-Contract
(same public method); capture awarded value + L1 where defproc publishes them, else keep the
buyer contact. scraper/index_lpp.py — build the prebuilt MiniSearch index
data/lpp-index.json (+ records) for the archive corpus (mid-size ~15k, pure static).
Wire the dashboard's LPP Finder view to data/lpp-index.json; verify item search, the
§5.33.4 vintage flag, and the DPMF 5 Ser 7 / DPMF 7 export (per DPM_LPP_MAPPING.md).
Final end-to-end pass. With all per-phase tests green, run the whole chain once (live scrape

archive/AoC → enrich → classify → geocode → diff/retain → index → write tenders.json &
lpp-index.json → load the dashboard) and confirm: live stream + sovereign map render with
correct criticality and retention; LPP Finder returns real bids with working defproc links and a
valid DPM export. Report the E2E result.





When done, show me: the step-2 live-site findings; the repo tree; a sample of the generated
tenders.json (5–10 real records, with their criticality); and the exact commands to (a) run the
pipeline locally and (b) connect the repo to Vercel/Netlify so the public dashboard goes live.

The deployed dashboard is a static, public, view-only site — no backend, no API keys, no secrets.
The only component that reaches defproc.gov.in is the scraper in GitHub Actions (open internet by
default). If your sandbox here can't reach defproc.gov.in for the one-time local test scrape, build
everything else and say so — the scheduled Action will still produce the first real data once pushed.