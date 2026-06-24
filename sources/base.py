"""Shared helpers: HTTP, normalization, classification, dedup keys.

Every source adapter returns a list of *normalized job dicts* built with
`make_job(...)`. scrape.py then filters, dedups, and writes them out.
"""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import requests

# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
_session = requests.Session()
_session.headers.update({"User-Agent": _UA, "Accept": "application/json"})


def get_json(url, params=None, timeout=25, retries=3, backoff=2.0):
    """GET a URL and parse JSON, with simple retry. Raises on final failure."""
    last = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            # 404 / 401 etc. -> don't retry these, they won't change
            if r.status_code in (401, 403, 404, 410):
                raise requests.HTTPError(f"{r.status_code} for {url}")
            last = requests.HTTPError(f"{r.status_code} for {url}")
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(backoff * (attempt + 1))
    raise last if last else RuntimeError(f"failed: {url}")


# --------------------------------------------------------------------------- #
# Time helpers
# --------------------------------------------------------------------------- #
def now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ts_to_iso(ts) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return None


def iso_to_ts(s) -> int | None:
    """Parse an ISO-8601 string (with or without tz) to unix seconds."""
    if not s:
        return None
    try:
        s = s.strip()
        # Python's fromisoformat handles offsets like +00:00; normalize Z
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Classification keyword sets
# --------------------------------------------------------------------------- #
CATEGORY_KEYWORDS = {
    "ai_ml": [
        "machine learning", "deep learning", " ai ", "a.i.", "artificial intelligence",
        "ml engineer", "ml eng", "mlops", "ml ops", "nlp", "natural language",
        "computer vision", " cv ", "llm", "large language", "generative", "gen ai",
        "genai", "ml infra", "ml platform", "perception", "speech", "recommendation",
        "deep neural", "reinforcement learning", "ml ", " ml/", "/ml",
    ],
    "research": [
        "research", "applied scientist", "research scientist", "research engineer",
        "research intern", "scientist", "phd",
    ],
    "data_science": [
        "data scientist", "data science", "decision scientist", "ds intern",
    ],
    "data_analytics": [
        "data analyst", "data analytics", "business intelligence", " bi ",
        "analytics engineer", "insights analyst", "reporting analyst",
        "business analyst", "quantitative analyst",
    ],
    "software": [
        "software engineer", "software developer", "software dev", "swe", "sde",
        "backend", "back-end", "back end", "frontend", "front-end", "front end",
        "full stack", "full-stack", "fullstack", "platform engineer",
        "infrastructure engineer", "systems engineer", "developer", "programmer",
        "devops", "site reliability", "sre", "embedded", "mobile engineer",
        "ios engineer", "android engineer", "cloud engineer", "security engineer",
    ],
    "webdev": [
        "web developer", "web engineer", "frontend", "front-end", "react",
        "ui engineer", "ux engineer", "full stack web",
    ],
    "quant": [
        "quant", "quantitative", "quantitative research", "quant trader",
        "quantitative developer", "trading",
    ],
}

# short tokens that must match on word boundaries to avoid false positives
_SHORT_TOKENS = {" ai ", " ml ", " cv ", " bi ", " ds ", "swe", "sde", "sre"}

# Word-boundary regex so "intern" matches intern/interns/internship but NOT
# "internal" / "international" / "internet" (which were false-positiving before).
_INTERN_RE = re.compile(
    r"\b(?:intern(?:s|ship|ships)?|co ?op|coop|apprentice\w*|practicum|trainee|"
    r"working student|summer ?20\d\d|fall ?20\d\d|spring ?20\d\d|winter ?20\d\d)\b"
)


def _is_intern(norm_text: str) -> bool:
    return bool(_INTERN_RE.search(norm_text))
_NEWGRAD_KW = [
    "new grad", "new graduate", "newgrad", "university grad", "university graduate",
    "early career", "early-career", "entry level", "entry-level", "campus",
    "graduate program", "grad program", "rotational", "recent graduate",
    "grad 20", "class of 20", "associate ", "junior", "early talent",
    "emerging talent", "university hire",
]
_SENIOR_KW = [
    "senior", "staff ", "principal", "lead ", " lead", "manager", "director",
    "vp ", "vice president", "head of", "distinguished", "fellow", "architect",
    "expert", " sr.", " sr ", "sr.", "experienced",
]


def _norm(text: str) -> str:
    return f" {re.sub(r'[^a-z0-9+/. ]', ' ', (text or '').lower())} "


def classify_categories(title: str, extra: str = "") -> list[str]:
    t = _norm(f"{title} {extra}")
    cats = []
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in _SHORT_TOKENS:
                if kw in t:
                    cats.append(cat)
                    break
            elif kw.strip() in t:
                cats.append(cat)
                break
    return cats


def classify_role_type(title: str, default: str | None = None) -> str:
    t = _norm(title)
    if _is_intern(t):
        return "internship"
    if any(k in t for k in _NEWGRAD_KW):
        return "new_grad"
    return default or "unknown"


def is_senior(title: str) -> bool:
    t = _norm(title)
    if "senior" in t or "staff" in t or "principal" in t or "director" in t:
        return True
    return any(k in t for k in _SENIOR_KW)


def is_early_career(title: str) -> bool:
    """For ATS sources: keep only intern / new-grad / junior roles."""
    t = _norm(title)
    intern = _is_intern(t)
    newgrad = any(k in t for k in _NEWGRAD_KW)
    if not (intern or newgrad):
        return False
    # interns and explicit "new grad" always qualify; otherwise drop senior titles
    if intern or "new grad" in t or "new graduate" in t:
        return True
    return not is_senior(title)


_SPONSOR_MAP = {
    "offers sponsorship": "offers",
    "does not offer sponsorship": "no_sponsorship",
    "u.s. citizenship is required": "citizen_required",
    "us citizenship is required": "citizen_required",
}


def classify_sponsorship(raw: str | None) -> str:
    if not raw:
        return "unknown"
    return _SPONSOR_MAP.get(raw.strip().lower(), "unknown")


# --------------------------------------------------------------------------- #
# Location / US detection
# --------------------------------------------------------------------------- #
_US_STATES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
    "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
    "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok",
    "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
    "wi", "wy", "dc",
}
_NON_US = [
    "canada", "united kingdom", "england", "scotland", "ireland", "india",
    "germany", "france", "spain", "italy", "netherlands", "poland", "sweden",
    "switzerland", "australia", "singapore", "japan", "china", "korea",
    "brazil", "mexico", "israel", "uae", "dubai", "portugal", "romania",
    "ukraine", "philippines", "vietnam", "indonesia", "argentina", "norway",
    "denmark", "finland", "belgium", "austria", "czech", "hungary", "greece",
    "turkey", "egypt", "nigeria", "kenya", "south africa", "new zealand",
    "hong kong", "taiwan", "thailand", "malaysia", "colombia", "chile",
    "toronto", "vancouver", "london", "bangalore", "bengaluru", "hyderabad",
    "mumbai", "delhi", "pune", "chennai", "berlin", "munich", "paris",
    "amsterdam", "dublin", "tel aviv", "sydney", "tokyo", "beijing",
    "shanghai", "seoul", "warsaw", "barcelona", "madrid", "zurich",
]


def location_info(locations, country: str | None = None):
    """Return (location_str, is_us, is_remote)."""
    locs = [str(l).strip() for l in (locations or []) if l and str(l).strip()]
    text = ", ".join(dict.fromkeys(locs))  # de-dup while preserving order
    low = f" {text.lower()} "
    is_remote = "remote" in low
    if country:
        c = country.strip().lower()
        is_us = c in {"united states", "usa", "us", "u.s.", "u.s", "united states of america"}
        return text or ("Remote" if is_remote else ""), is_us, is_remote

    has_state = bool(re.search(r"\b(" + "|".join(_US_STATES) + r")\b", low))
    has_usname = "united states" in low or " usa " in low or re.search(r"\bu\.?s\.?\b", low)
    foreign = any(c in low for c in _NON_US)

    if foreign and not (has_state or has_usname):
        is_us = False
    elif has_state or has_usname:
        is_us = True
    elif is_remote:
        is_us = True  # assume US-remote unless a foreign locale was named
    else:
        is_us = True  # blank/unknown -> keep (curated repos are US-centric)
    return text, is_us, is_remote


# --------------------------------------------------------------------------- #
# Canonical URL + stable id
# --------------------------------------------------------------------------- #
def canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlsplit(url.strip())
        # drop query + fragment, normalize trailing slash, lowercase host
        path = p.path.rstrip("/")
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, "", ""))
    except Exception:  # noqa: BLE001
        return url.strip()


def stable_id(company: str, title: str, url: str) -> str:
    cu = canonical_url(url)
    basis = cu if cu.startswith("http") else f"{(company or '').lower()}|{(title or '').lower()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Job factory
# --------------------------------------------------------------------------- #
def make_job(*, title, company, url, source, source_type,
             company_url=None, locations=None, country=None,
             date_posted_ts=None, date_updated_ts=None,
             sponsorship_raw=None, sponsorship=None,
             role_default=None, category_hint=""):
    title = (title or "").strip()
    company = (company or "").strip()
    loc_str, is_us, is_remote = location_info(locations, country)
    cats = classify_categories(title, category_hint)
    role = classify_role_type(title, role_default)
    spons = sponsorship if sponsorship else classify_sponsorship(sponsorship_raw)
    return {
        "id": stable_id(company, title, url),
        "title": title,
        "company": company,
        "company_url": company_url,
        "location": loc_str,
        "locations": locations or [],
        "url": url,
        "source": source,
        "source_type": source_type,
        "date_posted_ts": int(date_posted_ts) if date_posted_ts else None,
        "date_posted": ts_to_iso(date_posted_ts),
        "date_updated": ts_to_iso(date_updated_ts),
        "categories": cats,
        "role_type": role,
        "sponsorship": spons,
        "remote": is_remote,
        "is_us": is_us,
    }
