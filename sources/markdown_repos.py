"""Parser for curated repos that publish a markdown TABLE (not listings.json):
jobright-ai, speedyapply, sndsh404, zapplyjobs.

Config (config/markdown_repos.yaml) gives, per repo: the header signature to
locate the table, column indices, the date format, and a few quirks
('carry_forward' for jobright's '↳' = same-company-as-above).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .base import get_text, make_job, now_ts

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _row_cells(line):
    line = line.strip()
    if not line.startswith("|"):
        return None
    parts = line.split("|")[1:-1]  # drop the empty edges
    return [p.strip() for p in parts]


def _links(cell):
    out = []
    for m in re.finditer(r"\[([^\]]*)\]\((https?://[^)\s]+)\)", cell):           # md
        out.append(m.group(2))
    for m in re.finditer(r'<a[^>]*href=["\'](https?://[^"\']+)["\']', cell, re.I):  # html
        out.append(m.group(1))
    if not out:
        m = re.search(r"(https?://[^\s)|<>\"']+)", cell)                          # bare
        if m:
            out.append(m.group(1))
    return out


def _text(cell):
    s = re.sub(r"<[^>]+>", "", cell)                       # strip html tags
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)         # md link -> its text
    s = s.replace("**", "").replace("`", "").replace("*", "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _is_sep(cells):
    return cells and all(set(c) <= set("-: ") for c in cells)


def _parse_mon_dd(s, now):
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})", s)
    if not m:
        return None
    mon = _MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    day = int(m.group(2))
    year = datetime.fromtimestamp(now, tz=timezone.utc).year
    try:
        ts = int(datetime(year, mon, day, tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None
    if ts > now + 2 * 86400:     # date is in the "future" -> it was last year
        ts = int(datetime(year - 1, mon, day, tzinfo=timezone.utc).timestamp())
    return ts


def _parse_age(s, now):
    m = re.search(r"(\d+)\s*(h|d|w|mo|m|y)\b", s.lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    secs = {"h": 3600, "d": 86400, "w": 604800, "mo": 2592000,
            "m": 2592000, "y": 31536000}[unit]
    return now - n * secs


def _parse_iso(s):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        return int(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def _parse_date(s, kind, now):
    s = (s or "").strip()
    if not s or s in ("-", "—", "–", "N/A", "TBD"):
        return None
    if kind == "mon_dd":
        return _parse_mon_dd(s, now)
    if kind == "age":
        return _parse_age(s, now)
    # auto: try everything
    return _parse_iso(s) or _parse_age(s, now) or _parse_mon_dd(s, now)


def _visa(cell):
    t = _text(cell).lower()
    if any(k in t or k in cell for k in ("✅", "yes", "sponsor")):
        return "offers"
    if any(k in t or k in cell for k in ("❌", "no ", "no sponsor")):
        return "no_sponsorship"
    return "unknown"


def fetch(cfg):
    """cfg: name, url, default_role, header, idx{company,role,location,apply,date},
    date_kind, carry_forward(bool), hint(str), visa_idx(optional)."""
    text = get_text(cfg["url"])
    lines = text.splitlines()
    header_sig = [h.lower() for h in cfg["header"]]
    idx = cfg["idx"]
    ncols = max(idx.values()) + 1

    # locate the header row
    start = None
    for i, line in enumerate(lines):
        cells = _row_cells(line)
        if not cells:
            continue
        low = [_text(c).lower() for c in cells]
        if all(any(sig in c for c in low) for sig in header_sig) and len(cells) >= ncols:
            start = i
            break
    if start is None:
        return []

    now = now_ts()
    jobs, last_company = [], ""
    # These READMEs are multi-section (### FAANG, ### Quant, …), each an
    # independent table with the SAME schema separated by headings/blanks/HTML
    # comments. Scan to EOF, skipping non-table lines, separators, and the
    # repeated per-section header rows — don't stop at the first blank line.
    # ponytail: reads every same-schema table after the first header; a repo
    # with a trailing UNRELATED >=ncols table would over-collect — none do today.
    for line in lines[start + 1:]:
        cells = _row_cells(line)
        if cells is None:
            continue                    # section heading / blank / HTML comment
        if _is_sep(cells):
            continue
        if len(cells) < ncols:
            continue
        low = [_text(c).lower() for c in cells]
        if all(any(sig in c for c in low) for sig in header_sig):
            continue                    # repeated per-section header row

        company = _text(cells[idx["company"]])
        if cfg.get("carry_forward") and (company in ("↳", "⤷", "") or company.startswith("↳")):
            company = last_company
        elif company:
            last_company = company

        title = _text(cells[idx["role"]])
        links = _links(cells[idx["apply"]])
        url = links[0] if links else ""
        if not title or not url or not company:
            continue

        loc = _text(cells[idx["location"]]) if "location" in idx else ""
        posted = _parse_date(cells[idx["date"]], cfg.get("date_kind", "auto"), now) if "date" in idx else None
        spons = _visa(cells[cfg["visa_idx"]]) if cfg.get("visa_idx") is not None and len(cells) > cfg["visa_idx"] else None

        jobs.append(make_job(
            title=title,
            company=company,
            url=url,
            locations=[loc] if loc else [],
            source=f"github:{cfg['name']}",
            source_type="markdown_repo",
            date_posted_ts=posted,
            role_default=cfg.get("default_role"),
            sponsorship=spons,
            category_hint=cfg.get("hint", ""),
        ))
    return jobs
