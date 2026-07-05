"""Polite, public-endpoint-only GET layer for defproc.gov.in (NIC GePNIC).

HARD RULES enforced here (see CLAUDE.md "scraping ethics" and design doc §3):

  * Public listing + detail GETs only. We crawl the Home latest-tenders feed and
    the by-organisation / by-location / by-date / Tenders-in-Archive /
    Results-of-Tenders drill-downs (all CAPTCHA-free), plus the per-tender detail
    pages linked from them.
  * We NEVER submit the keyword Search form, NEVER log in, NEVER download bid
    documents, and NEVER solve, OCR, or replay a CAPTCHA. Endpoints that are
    CAPTCHA/login/download gated are blocked here by URL deny-list — the request
    is refused, not bypassed.
  * One worker, >= MIN_DELAY seconds between requests, descriptive User-Agent,
    one pass per cron tick.

Live-verified note (2026-06-28): on this GePNIC instance the link labelled
"Active Tenders" (page=FrontEndLatestActiveTenders) renders a CAPTCHA-gated
keyword Search form, NOT an open table — so it is on the deny-list. The open,
indexable feed is the Home page latest-tenders widget and the by-* drill-downs.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "defproc-monitor/0.1"
ORIGIN = "https://defproc.gov.in"
BASE = "https://defproc.gov.in/nicgep/app"
ALLOWED_HOST = "defproc.gov.in"   # scraper may reach ONLY this host (anti-SSRF)
MIN_DELAY = 3.0  # seconds between requests — politeness hard rule (>= 3 s)

# defproc exposes NO stable per-tender URL — every detail link is session-scoped
# ($DirectLink&session=T&sp=…) and dies with the scraper's session. So the public
# dashboard links to the durable Tender-Status lookup page; the viewer pastes the
# Tender ID (shown on the card) and solves the one captcha there. Human-in-the-loop
# by necessity, never a CAPTCHA bypass.
TENDER_LOOKUP_URL = BASE + "?page=WebTenderStatusLists&service=page"

# Public, CAPTCHA-free entry points we are allowed to crawl.
ENTRY_POINTS = {
    "home": "?page=Home&service=page",
    "by_organisation": "?page=FrontEndTendersByOrganisation&service=page",
    "by_location": "?page=FrontEndTendersByLocation&service=page",
    "by_date": "?page=FrontEndListTendersbyDate&service=page",
    "archive": "?page=FrontEndTendersInArchive&service=page",
    "results": "?page=ResultOfTenders&service=page",
}

# URL substrings we refuse to fetch: CAPTCHA keyword-search, login, doc-download.
# This is a deterministic guardrail, not advisory prose.
FORBIDDEN_URL_TOKENS = (
    "frontendadvancedsearch",       # keyword Search form (CAPTCHA-gated)
    "frontendlatestactivetenders",  # Active-Tenders = CAPTCHA search on this instance
    "login", "signin", "logon",
    "downloaddoc", "documentdownload", "directdownload", "downloadfile",
    "service=download",
)

log = logging.getLogger("defproc.fetch")


class GatedContent(Exception):
    """A page requires a CAPTCHA/login we will not bypass — caller degrades."""


class ForbiddenEndpoint(Exception):
    """Refused to fetch a CAPTCHA/login/document-download endpoint by policy."""


def is_forbidden_url(url: str) -> bool:
    low = url.lower()
    return any(tok in low for tok in FORBIDDEN_URL_TOKENS)


def is_allowed_host(url: str) -> bool:
    """Only defproc.gov.in (and its subdomains) may be fetched — a scraped/
    injected off-site href must never send the crawler elsewhere (anti-SSRF)."""
    host = (urlparse(url).hostname or "").lower()
    return host == ALLOWED_HOST or host.endswith("." + ALLOWED_HOST)


class Fetcher:
    """Single-worker, rate-limited HTTP GET with a hard policy deny-list."""

    def __init__(self, min_delay: float = MIN_DELAY, session: requests.Session | None = None):
        self.min_delay = min_delay
        self.s = session or requests.Session()
        self.s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-IN,en;q=0.9",
        })
        self._last = 0.0
        self.count = 0

    def _wait(self) -> None:
        dt = time.monotonic() - self._last
        if dt < self.min_delay:
            time.sleep(self.min_delay - dt)

    def get(self, url: str) -> requests.Response:
        """GET a public page. Refuses off-host + forbidden endpoints; delays."""
        if not is_allowed_host(url):
            raise ForbiddenEndpoint(f"policy: refusing off-site host -> {url}")
        if is_forbidden_url(url):
            raise ForbiddenEndpoint(f"policy: refusing CAPTCHA/login/download endpoint -> {url}")
        self._wait()
        try:
            r = self.s.get(url, timeout=30)
        finally:
            self._last = time.monotonic()
            self.count += 1
        r.raise_for_status()
        return r

    def get_entry(self, name: str) -> requests.Response:
        if name not in ENTRY_POINTS:
            raise KeyError(f"unknown entry point: {name}")
        # Prime a session cookie via Home once (GePNIC issues JSESSIONID there).
        return self.get(BASE + ENTRY_POINTS[name])

    def absolutize(self, href: str) -> str:
        return urljoin(ORIGIN + "/", href.lstrip("/")) if not href.startswith("http") else href


def looks_like_captcha_wall(html: str) -> bool:
    """True only when the MAIN content is a CAPTCHA challenge (gated detail/listing).

    Every GePNIC page embeds a small CAPTCHA search widget in a side panel, so
    mere presence of 'Enter Captcha' is NOT gating. We treat a page as walled
    only when it has the challenge text but none of the real content markers a
    listing/detail page would carry.
    """
    low = html.lower()
    has_captcha = ("enter captcha" in low) or ("provide captcha" in low)
    has_content = any(m in low for m in (
        "td_caption", "td_field",        # detail-page field table
        "tender title", "reference no",  # listing table header
        "organisation chain",
    ))
    return has_captcha and not has_content
