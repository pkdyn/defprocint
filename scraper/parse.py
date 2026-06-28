"""All defproc/GePNIC HTML parsing lives here (the portal changes; fixes stay
one-file). Verified against live fixtures captured 2026-06-28:
  tests/fixtures/live_home.html    -> latest-tenders listing widget
  tests/fixtures/live_detail.html  -> per-tender detail page (td_caption/td_field)

Listing table header (Home / by-* drill-downs):
    Tender Title | Reference No | Closing Date | Bid Opening Date
each row's title links via a session-scoped $DirectLink to its detail page.

Detail page exposes td_caption -> td_field pairs:
    Tender ID, Organisation Chain ('||'-delimited), Tender Type (mode),
    Tender Category, Tender Value in ₹, Work Description, Location, ...
plus a "Tender Inviting Authority" block: Name / Address / Pin.
"""
from __future__ import annotations

import html as ihtml
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

_MONTHS: list[str] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH_NUM = {m: i + 1 for i, m in enumerate(_MONTHS)}
_ID_RE = re.compile(r"\b\d{4}_[A-Za-z0-9]+_\d+_\d+\b")
_ROWNUM_RE = re.compile(r"^\s*\d+\.\s*")
_DT_RE = re.compile(r"(\d{2})-([A-Za-z]{3})-(\d{4})(?:\s+(\d{1,2}):(\d{2})\s*([AP]M))?")


# --------------------------------------------------------------------------- #
# small field helpers
# --------------------------------------------------------------------------- #
def clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", ihtml.unescape(s)).strip()


def org_chain_clean(s: Optional[str]) -> str:
    """'A||B||C' (GePNIC) -> 'A ▸ B ▸ C' (dashboard separator)."""
    s = clean_text(s)
    if not s:
        return ""
    parts = [p.strip() for p in re.split(r"\|\|", s) if p.strip()]
    return " ▸ ".join(parts) if parts else s


def parse_indian_number(s: Optional[str]) -> Optional[int]:
    """'17,00,000' / '₹ 45,00,000.00' -> int rupees. 'NA'/'' -> None."""
    if not s:
        return None
    s = clean_text(s)
    digits = re.sub(r"[^\d.]", "", s)
    if not digits or digits in (".",):
        return None
    try:
        return int(round(float(digits)))
    except ValueError:
        return None


def parse_gepnic_datetime(s: Optional[str]) -> Optional[datetime]:
    """'18-Jul-2026 06:00 PM' / '18-Jul-2026' -> datetime (None if unparseable)."""
    if not s:
        return None
    m = _DT_RE.search(clean_text(s))
    if not m:
        return None
    dd, mon, yyyy, hh, mm, ap = m.groups()
    month = _MONTH_NUM.get(mon.title())
    if month is None:
        return None
    hour, minute = 0, 0
    if hh:
        hour, minute = int(hh) % 12, int(mm)
        if ap.upper() == "PM":
            hour += 12
    try:
        return datetime(int(yyyy), month, int(dd), hour, minute)
    except ValueError:
        return None


def closing_display(s: Optional[str]) -> str:
    """'18-Jul-2026 06:00 PM' -> '18 Jul' (dashboard closing_date display)."""
    dt = parse_gepnic_datetime(s)
    return f"{dt.day:02d} {_MONTHS[dt.month - 1]}" if dt else clean_text(s)


# --------------------------------------------------------------------------- #
# listing parse  (Home latest-tenders widget + by-* drill-downs share layout)
# --------------------------------------------------------------------------- #
def _find_listing_table(soup: BeautifulSoup):
    """Innermost table whose header is Tender Title / Reference No / Closing Date."""
    best = None
    for t in soup.find_all("table"):
        head = " ".join(c.get_text(" ", strip=True) for c in t.find_all(["th", "td"])[:8]).lower()
        if "tender title" in head and "reference no" in head and "closing date" in head:
            nested = len(t.find_all("table"))
            if best is None or nested < best[1]:
                best = (t, nested)
    return best[0] if best else None


def parse_listing(html: str, origin: str = "https://defproc.gov.in") -> list[dict]:
    """Listing HTML -> rows: {title, ref_no, closing_date(display), closing_dt,
    opening_date, detail_url}. detail_url is the row's $DirectLink (absolute)."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_listing_table(soup)
    rows: list[dict] = []
    if table is None:
        return rows
    # GePNIC nests the data rows inside a wrapper <tr>; use DIRECT-child cells so
    # we read the real 4-column rows, not the flattened wrapper.
    for tr in table.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 4:
            continue
        cells = [c.get_text(" ", strip=True) for c in tds]
        if not _ROWNUM_RE.match(cells[0]):
            continue
        title = clean_text(_ROWNUM_RE.sub("", cells[0]))
        a = tr.find("a", href=True)
        href = ihtml.unescape(str(a["href"])) if a else ""
        detail_url = href if href.startswith("http") else (origin.rstrip("/") + "/" + href.lstrip("/")) if href else ""
        closing_raw = cells[2]
        rows.append({
            "title": title,
            "ref_no": clean_text(cells[1]),
            "closing_date": closing_display(closing_raw),
            "closing_dt": parse_gepnic_datetime(closing_raw),
            "opening_date": clean_text(cells[3]),
            "detail_url": detail_url,
        })
    return rows


# --------------------------------------------------------------------------- #
# by-organisation drill-down  (richer than the Home widget — dates + org inline)
# header: S.No | e-Published Date | Closing Date | Opening Date | Title+Ref | Org
# --------------------------------------------------------------------------- #
def find_org_count_links(html: str, origin: str = "https://defproc.gov.in") -> list[dict]:
    """Org-tree '<count>'-as-link entries -> {count, url, name}. The tree row is
    [S.No, Organisation, Count]; the name seeds org_chain for that org's tenders."""
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if not re.search(r"DirectLink|service=direct", href):
            continue
        txt = clean_text(a.get_text(" ", strip=True)).replace(",", "")
        if not txt.isdigit() or int(txt) <= 0:
            continue
        url = ihtml.unescape(str(href))
        url = url if url.startswith("http") else origin.rstrip("/") + "/" + url.lstrip("/")
        if url in seen:
            continue
        seen.add(url)
        name = ""
        tr = a.find_parent("tr")
        if tr:
            for c in tr.find_all("td"):
                ct = clean_text(c.get_text(" ", strip=True))
                if ct and not ct.replace(",", "").isdigit() and len(ct) > 3:
                    name = ct
                    break
        out.append({"count": int(txt), "url": url, "name": name})
    return out


def _find_org_listing_table(soup: BeautifulSoup):
    for t in soup.find_all("table"):
        head = " ".join(c.get_text(" ", strip=True) for c in t.find_all(["th", "td"])[:12]).lower()
        if "e-published" in head and "closing date" in head and "s.no" in head:
            return t
    return None


def parse_org_listing(html: str, origin: str = "https://defproc.gov.in") -> list[dict]:
    """by-organisation tender-list HTML -> rich rows:
    {title, ref_no, published_date, closing_date(display), closing_dt,
     opening_date, org_chain, detail_url}."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_org_listing_table(soup)
    rows: list[dict] = []
    if table is None:
        return rows
    for tr in table.find_all("tr"):
        tds = tr.find_all("td", recursive=False) or tr.find_all("td")
        if len(tds) < 6 or not tds[0].get_text(strip=True).isdigit():
            continue
        a = tr.find("a", href=True)
        if not a:
            continue
        title = clean_text(a.get_text(" ", strip=True)).strip("[]").strip()
        cell = clean_text(tds[4].get_text(" ", strip=True))
        ref = cell.replace(a.get_text(" ", strip=True), "").strip(" []").strip()
        href = ihtml.unescape(str(a["href"]))
        detail_url = href if href.startswith("http") else origin.rstrip("/") + "/" + href.lstrip("/")
        closing_raw = clean_text(tds[2].get_text(" ", strip=True))
        published_raw = clean_text(tds[1].get_text(" ", strip=True))
        rows.append({
            "title": title,
            "ref_no": ref,
            "published_date": published_raw,
            "published_dt": parse_gepnic_datetime(published_raw),
            "closing_date": closing_display(closing_raw),
            "closing_dt": parse_gepnic_datetime(closing_raw),
            "opening_date": clean_text(tds[3].get_text(" ", strip=True)),
            "org_chain": org_chain_clean(tds[5].get_text(" ", strip=True)),
            "detail_url": detail_url,
        })
    return rows


# --------------------------------------------------------------------------- #
# detail parse  (td_caption -> td_field pairs + Tender Inviting Authority block)
# --------------------------------------------------------------------------- #
def _caption_field_map(soup: BeautifulSoup) -> dict:
    out: dict[str, str] = {}
    cells = soup.find_all("td")
    for i, td in enumerate(cells):
        cls = td.get("class") or []
        if "td_caption" in cls:
            label = clean_text(td.get_text(" ", strip=True)).rstrip(":")
            # value = next td_field sibling/cell
            val = ""
            for nxt in cells[i + 1:i + 3]:
                if "td_field" in (nxt.get("class") or []):
                    val = clean_text(nxt.get_text(" ", strip=True))
                    break
            if label and label not in out:
                out[label] = val
    return out


def _parse_tia_block(soup: BeautifulSoup) -> dict:
    """Extract Tender Inviting Authority Name / Address / Pin from its sub-block."""
    text = soup.get_text("\n", strip=True)
    i = text.find("Tender Inviting Authority")
    out = {"tia_name": "", "buyer_address": "", "pincode": ""}
    if i < 0:
        return out
    chunk = text[i:i + 600]
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    # lines ~ ['Tender Inviting Authority','Name', <name>, 'Address', <addr...>, 'Pin 786 189', ...]
    def grab(after_label):
        for k, ln in enumerate(lines):
            if ln.lower() == after_label:
                return lines[k + 1] if k + 1 < len(lines) else ""
        return ""
    out["tia_name"] = grab("name")
    # address = lines between 'Address' and the Pin/footer
    addr_lines = []
    started = False
    for ln in lines:
        low = ln.lower()
        if low == "address":
            started = True
            continue
        if not started:
            continue
        if low.startswith("pin") or low in ("back", "visitor no") or low.startswith("visitor no"):
            break
        addr_lines.append(ln)
    out["buyer_address"] = clean_text(", ".join(addr_lines))
    mpin = re.search(r"Pin\s*[:\-]?\s*([\d\s]{6,9})", chunk, re.I)
    if mpin:
        out["pincode"] = re.sub(r"\D", "", mpin.group(1))[:6]
    return out


def parse_detail(html: str) -> dict:
    """Detail HTML -> enrichment dict. Returns {} for a gated/empty page so the
    caller can degrade. Keys: tender_id, org_chain, location, tender_type,
    category, product_category, value_inr, description, title, tia_name,
    buyer_address, pincode."""
    soup = BeautifulSoup(html, "html.parser")
    fields = _caption_field_map(soup)
    # A real detail page always carries a canonical tender id (YYYY_ORG_NNN_N).
    # Its absence => gated/empty/search page; return {} so the caller degrades.
    m = _ID_RE.search(html)
    if not fields or not m:
        return {}
    tender_id = fields.get("Tender ID", "")
    if not _ID_RE.match(tender_id or ""):
        tender_id = m.group(0)

    tia = _parse_tia_block(soup)
    location = fields.get("Location", "")
    # GePNIC 'Location' is sometimes empty/noisy; fall back later from address/pin.
    if location.lower() in ("", "na", "tenders in archive"):
        location = ""

    return {
        "tender_id": tender_id,
        "org_chain": org_chain_clean(fields.get("Organisation Chain", "")),
        "location": location,
        "tender_type": clean_text(fields.get("Tender Type", "")),
        "category": clean_text(fields.get("Tender Category", "")),
        "product_category": clean_text(fields.get("Product Category", "")),
        "value_inr": parse_indian_number(fields.get("Tender Value in ₹")
                                         or fields.get("Tender Value in Rs.")),
        "description": clean_text(fields.get("Work Description", "") or fields.get("Title", "")),
        "title": clean_text(fields.get("Title", "") or fields.get("Work Description", "")),
        "tia_name": tia["tia_name"],
        "buyer_address": tia["buyer_address"],
        "pincode": tia["pincode"],
    }
