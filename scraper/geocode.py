"""Offline coarse geocoder: triangulate a tender's location from every field
defproc gives us, in order of precision. All offline, free, stdlib-only.

geocode_record() resolution order (best signal wins, then falls back):
  1. exact pincode in data/pincodes.csv (India Post directory subset)
  2. place name found in buyer_address  (e.g. 'Dist Tinsukia', 'Cantt Kanpur')
  3. place name in the org-chain tail    (e.g. 'CE SHILLONG ZONE' -> Shillong)
  4. explicit location field
  5. place name anywhere in the title    (e.g. 'AFS KUMBHIRGRAM')
  6. PIN first-2-digit postal-circle centroid (always in-country)
We use whatever is remotely relevant to triangulate; if nothing resolves we
return (None, None) and the dashboard simply omits the marker.
"""
from __future__ import annotations

import csv
import json
import os
import re
import time
from typing import Optional

_DATADIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DATA = os.path.join(_DATADIR, "pincodes.csv")

# --- online geocoder (free, no key): OpenStreetMap Nominatim -----------------
# Runs ONLY in the scraper (GitHub Actions), NEVER the dashboard, so the static
# site still makes zero outbound calls. Results are cached to data/geocache.json
# (committed) so we don't re-query and we stay well within Nominatim's 1 req/s.
# Enable with DEFPROC_GEOCODE_ONLINE=1; off by default (tests stay offline).
ONLINE = os.environ.get("DEFPROC_GEOCODE_ONLINE", "").lower() not in ("", "0", "false", "no")
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_DELAY = 1.1
_CACHE_PATH = os.path.join(_DATADIR, "geocache.json")
_geocache: Optional[dict] = None
_last_online = [0.0]

# Defence-relevant gazetteer: cantonments, command HQs, naval/AF stations, district
# HQs, major cities. Keys are lowercase; aliases included. (lat, lng).
CITY_COORDS = {
    "new delhi": (28.613, 77.209), "delhi": (28.613, 77.209), "dhaula kuan": (28.59, 77.16),
    "pune": (18.520, 73.857), "khadki": (18.563, 73.853), "kirkee": (18.563, 73.853),
    "dehu road": (18.71, 73.76), "deolali": (19.94, 73.83), "devlali": (19.94, 73.83),
    "nashik": (20.00, 73.79), "nasik": (20.00, 73.79), "ahmednagar": (19.09, 74.74),
    "aurangabad": (19.88, 75.34), "nagpur": (21.15, 79.09), "kamptee": (21.22, 79.20),
    "mumbai": (19.076, 72.877), "bombay": (19.076, 72.877), "colaba": (18.91, 72.81),
    "mankhurd": (19.047, 72.92), "secunderabad": (17.44, 78.50), "hyderabad": (17.39, 78.49),
    "bengaluru": (12.97, 77.59), "bangalore": (12.97, 77.59), "chennai": (13.083, 80.270),
    "wellington": (11.36, 76.79), "coimbatore": (11.02, 76.96), "trivandrum": (8.52, 76.94),
    "thiruvananthapuram": (8.52, 76.94), "kochi": (9.931, 76.267), "cochin": (9.931, 76.267),
    "kannur": (11.87, 75.37), "cannanore": (11.87, 75.37), "ezhimala": (12.020, 75.220),
    "mangaluru": (12.914, 74.856), "mangalore": (12.914, 74.856), "belgaum": (15.85, 74.50),
    "belagavi": (15.85, 74.50), "goa": (15.396, 73.812), "panaji": (15.49, 73.83),
    "vasco": (15.39, 73.82), "dabolim": (15.39, 73.82), "karwar": (14.813, 74.129),
    "visakhapatnam": (17.686, 83.218), "vizag": (17.686, 83.218), "vijayawada": (16.51, 80.65),
    "kolkata": (22.572, 88.363), "calcutta": (22.572, 88.363), "barrackpore": (22.76, 88.37),
    "panagarh": (23.45, 87.42), "siliguri": (26.73, 88.40), "sukna": (26.83, 88.39),
    "binnaguri": (26.78, 89.18), "hashimara": (26.74, 89.36), "tezpur": (26.633, 92.800),
    "misamari": (26.79, 92.50), "dinjan": (27.49, 95.36), "tinsukia": (27.49, 95.36),
    "lekhapani": (27.30, 95.75), "jorhat": (26.75, 94.20), "guwahati": (26.14, 91.74),
    "shillong": (25.57, 91.88), "silchar": (24.82, 92.80), "kumbhirgram": (24.91, 92.98),
    "imphal": (24.82, 93.94), "dimapur": (25.91, 93.73), "agartala": (23.83, 91.28),
    "itanagar": (27.100, 93.620), "leh": (34.152, 77.577), "srinagar": (34.083, 74.797),
    "udhampur": (32.92, 75.13), "jammu": (32.73, 74.87), "pathankot": (32.27, 75.65),
    "jalandhar": (31.33, 75.58), "amritsar": (31.63, 74.87), "ferozepur": (30.93, 74.61),
    "bathinda": (30.21, 74.95), "patiala": (30.34, 76.39), "ambala": (30.38, 76.78),
    "chandigarh": (30.740, 76.790), "chandimandir": (30.74, 76.95), "roorkee": (29.850, 77.890),
    "dehradun": (30.32, 78.03), "meerut": (28.98, 77.71), "bareilly": (28.36, 79.42),
    "agra": (27.18, 78.01), "kanpur": (26.45, 80.33), "lucknow": (26.85, 80.95),
    "prayagraj": (25.44, 81.85), "allahabad": (25.44, 81.85), "varanasi": (25.32, 82.97),
    "gorakhpur": (26.76, 83.37), "jhansi": (25.45, 78.57), "babina": (25.25, 78.47),
    "gwalior": (26.22, 78.18), "jabalpur": (23.18, 79.99), "bhopal": (23.26, 77.41),
    "mhow": (22.55, 75.76), "sagar": (23.84, 78.74), "jaipur": (26.92, 75.79),
    "jodhpur": (26.24, 73.02), "bikaner": (28.02, 73.31), "jaisalmer": (26.92, 70.91),
    "kota": (25.21, 75.86), "udaipur": (24.58, 73.71), "nasirabad": (26.30, 74.73),
    "ahmedabad": (23.03, 72.58), "jamnagar": (22.470, 70.057), "bhuj": (23.24, 69.67),
    "okha": (22.470, 69.071), "vadodara": (22.31, 73.18), "baroda": (22.31, 73.18),
    "ranchi": (23.34, 85.31), "ramgarh": (23.63, 85.52), "danapur": (25.63, 85.05),
    "patna": (25.59, 85.14), "cuttack": (20.46, 85.88), "bhubaneswar": (20.30, 85.82),
    "chandipur": (21.45, 87.02), "port blair": (11.623, 92.726), "pashan": (18.54, 73.79),
}

# PIN first-2-digit -> postal-circle centroid (coarse universal fallback).
PIN_PREFIX = {
    "11": (28.6, 77.2), "12": (29.0, 76.5), "13": (29.0, 76.5), "14": (30.9, 75.8),
    "15": (30.9, 75.8), "16": (30.7, 76.8), "17": (31.8, 77.2), "18": (33.3, 75.3),
    "19": (34.0, 74.8), "20": (27.5, 80.3), "21": (27.5, 80.0), "22": (28.0, 79.5),
    "23": (26.5, 80.5), "24": (27.0, 81.0), "25": (26.8, 80.9), "26": (26.5, 82.0),
    "27": (28.7, 77.8), "28": (27.2, 78.0), "30": (26.9, 75.8), "31": (27.5, 74.5),
    "32": (26.3, 73.0), "33": (24.6, 73.7), "34": (25.2, 75.8), "36": (22.3, 73.2),
    "37": (22.3, 71.0), "38": (23.0, 72.6), "39": (21.6, 73.0), "40": (19.2, 73.0),
    "41": (18.9, 74.5), "42": (19.8, 75.3), "43": (20.9, 77.0), "44": (21.1, 79.1),
    "45": (23.2, 77.4), "46": (23.5, 78.5), "47": (22.0, 79.0), "48": (21.2, 81.6),
    "49": (21.0, 82.0), "50": (17.4, 78.5), "51": (16.5, 79.5), "52": (16.0, 80.5),
    "53": (17.7, 83.3), "56": (12.97, 77.6), "57": (15.3, 76.0), "58": (15.4, 75.0),
    "59": (13.0, 74.8), "60": (13.08, 80.27), "61": (11.0, 78.0), "62": (10.8, 78.7),
    "63": (9.9, 78.1), "64": (11.0, 77.0), "67": (10.5, 76.2), "68": (9.5, 76.6),
    "69": (8.5, 77.0), "70": (22.57, 88.36), "71": (22.6, 88.4), "72": (23.2, 87.8),
    "73": (24.0, 88.0), "74": (26.7, 88.4), "75": (20.3, 85.8), "76": (21.5, 84.0),
    "77": (19.3, 84.8), "78": (26.2, 92.5), "79": (27.5, 94.5), "80": (25.6, 85.1),
    "81": (25.4, 86.5), "82": (24.8, 85.0), "83": (23.4, 85.3), "84": (24.8, 84.0),
    "85": (26.1, 86.5),
}

# longest place names first, so 'port blair' wins over 'blair', 'new delhi' over 'delhi'
_PLACES_BY_LEN = sorted(CITY_COORDS.keys(), key=len, reverse=True)


def _load_csv() -> dict:
    out: dict[str, tuple[float, float]] = {}
    if os.path.exists(_DATA):
        with open(_DATA, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                pin = (row.get("pincode") or "").strip()
                try:
                    out[pin] = (float(row["lat"]), float(row["lng"]))
                except (KeyError, ValueError, TypeError):
                    continue
    return out


_PINCODES = _load_csv()


def _scan_places(text: Optional[str]):
    """Return coords of the first (longest) gazetteer place found in text."""
    if not text:
        return None
    low = re.sub(r"\s+", " ", text.lower())
    for place in _PLACES_BY_LEN:
        if re.search(r"\b" + re.escape(place) + r"\b", low):
            return CITY_COORDS[place]
    return None


def geocode(pincode: Optional[str] = None, location: Optional[str] = None):
    """Back-compat: (lat,lng) from a pincode and/or a single location string."""
    pin = re.sub(r"\D", "", pincode or "")
    if pin and pin in _PINCODES:
        return _PINCODES[pin]
    hit = _scan_places(location)
    if hit:
        return hit
    if len(pin) >= 2 and pin[:2] in PIN_PREFIX:
        return PIN_PREFIX[pin[:2]]
    return (None, None)


def _load_cache() -> dict:
    global _geocache
    cache = _geocache
    if cache is None:
        try:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = {}
        _geocache = cache
    return cache


def save_cache() -> None:
    """Persist the geocode cache (call once at end of a scrape; commit it)."""
    if _geocache is not None:
        try:
            with open(_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(_geocache, f, ensure_ascii=False)
        except OSError:
            pass


def geocode_online(query: str):
    """Nominatim (free, no key) with cache + 1 req/s rate limit. (lat,lng)|None.
    A cached miss (null) is never retried; transient errors are not cached."""
    cache = _load_cache()
    key = re.sub(r"\s+", " ", query.strip().lower())
    if not key:
        return None
    if key in cache:
        v = cache[key]
        return tuple(v) if v else None
    try:
        import requests
        wait = _NOMINATIM_DELAY - (time.monotonic() - _last_online[0])
        if wait > 0:
            time.sleep(wait)
        r = requests.get(_NOMINATIM,
                         params={"q": query, "format": "json", "limit": 1, "countrycodes": "in"},
                         headers={"User-Agent": "defproc-monitor/0.1"}, timeout=20)
        _last_online[0] = time.monotonic()
        data = r.json() if r.ok else []
        if data:
            ll = [float(data[0]["lat"]), float(data[0]["lon"])]
            cache[key] = ll
            return (ll[0], ll[1])
        cache[key] = None  # genuine miss -> don't retry
    except Exception:
        return None
    return None


def _query_candidates(rec: dict) -> list[str]:
    """Progressively coarser Nominatim queries: full address (street precision if
    it resolves) -> bare pincode (resolves for ALL Indian PINs) -> city. Cryptic
    military addresses ('GE Dinjan') often miss, so the pincode is the workhorse."""
    addr = (rec.get("buyer_address") or "").strip()
    pin = re.sub(r"\D", "", rec.get("pincode") or "")
    loc = (rec.get("location") or "").strip()
    out = []
    if addr:
        out.append(f"{addr}, {pin}, India" if pin else f"{addr}, India")
    if pin:
        out.append(f"{pin}, India")
    if loc:
        out.append(f"{loc}, India")
    return out


def geocode_record(rec: dict):
    """Triangulate (lat, lng), most precise first:
    online (Nominatim full-address -> pincode -> city, if enabled) ->
    exact pincode CSV -> place-name scan (address/org/location/title) ->
    PIN-prefix centroid -> (None, None)."""
    if ONLINE:
        for q in _query_candidates(rec):
            hit = geocode_online(q)
            if hit:
                return hit
    pin = re.sub(r"\D", "", rec.get("pincode") or "")
    if pin and pin in _PINCODES:
        return _PINCODES[pin]
    for field in ("buyer_address", "org_chain", "location", "title"):
        hit = _scan_places(rec.get(field))
        if hit:
            return hit
    if len(pin) >= 2 and pin[:2] in PIN_PREFIX:
        return PIN_PREFIX[pin[:2]]
    return (None, None)
