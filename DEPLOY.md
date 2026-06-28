# Deploy — defproc-monitor

The site is the `web/` directory (static). The first commit already contains real
data (`web/tenders.json`, `web/lpp-index.json`), so the dashboard shows live
tenders the instant you deploy; the cron just refreshes it twice daily.

## (a) Run / refresh locally
```bash
pip install -r requirements.txt

# Live monitor → web/tenders.json  (by-organisation, published-in-72h window)
# DEFPROC_GEOCODE_ONLINE=1 turns on free OSM Nominatim geocoding (cached)
DEFPROC_GEOCODE_ONLINE=1 python -m scraper.pipeline --out web/tenders.json --retention-hours 72

# LPP reference index → web/lpp-index.json  (full active catalogue; ~15-25 min for the classifier)
python -m scraper.index_lpp --archive --enrich-cap 30

# Preview (serve web/ so ./tenders.json + ./lpp-index.json resolve)
python -m http.server -d web 8000        # → http://localhost:8000/

python -m pytest -q                       # 53 gates
```

## (b) Go live

```bash
# 1) Push to GitHub (you pick name/visibility). With gh CLI:
gh repo create defproc-monitor --private --source=. --remote=origin --push
#   …or manually:
#   git remote add origin git@github.com:<you>/defproc-monitor.git && git push -u origin main

# 2) Static host — pick one (site dir is web/):
npm i -g netlify-cli && netlify deploy --dir web --prod      # netlify.toml: publish=web + "/"→dashboard
#   or:  npm i -g vercel && vercel --prod                    # then Settings → Root Directory = web
#   or:  GitHub Pages → Settings ▸ Pages ▸ deploy /web

# 3) Turn on the cron (already wired in .github/workflows/scrape.yml, twice daily):
#    GitHub repo → Settings ▸ Actions ▸ "Workflow permissions" = Read and write   ← REQUIRED to commit
#    then Actions tab ▸ "scrape" ▸ Run workflow  (or just wait for the schedule)
```

## Three things to know
- **First commit already has real data** → the dashboard works immediately on deploy; the cron
  just refreshes `tenders.json` / `lpp-index.json` / `geocache.json` twice daily.
- **The cron commit step needs Actions ▸ Workflow permissions = "Read and write"** (GitHub defaults
  new repos to read-only). Without it, scrapes run but can't push.
- **CI** (`ci.yml`) runs the 53-test suite on every push. **The cron** (`scrape.yml`) does the
  geocode-online scrape + uncapped LPP build and commits the data.

## Notes
- Only the scraper (in GitHub Actions) reaches `defproc.gov.in`; the deployed page makes **no**
  outbound calls — it fetches only its own same-origin `tenders.json` / `lpp-index.json`.
- Scraping is polite + public-only (UA `defproc-monitor/0.1`, ≥3 s, one worker); all gated
  (CAPTCHA/login/download) endpoints are deny-listed and the limits are enforced by
  `tests/test_ethics_gates.py`.
- The "look up on defproc" links open the Tender-Status **search** page (the only cold-clickable
  page) and auto-copy the Tender ID / buyer reference for you to paste + solve the one captcha —
  defproc has no cold-clickable per-tender URL.
