"""Workday (myworkdayjobs) public cxs JSON API — covers big employers.

  POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
  body: {"appliedFacets":{}, "limit":20, "offset":N, "searchText":"intern"}
Response: {total, jobPostings:[{title, externalPath, locationsText, postedOn,...}]}
postedOn is relative text ("Posted 5 Days Ago") -> parsed to an approximate ts.
Boards are huge, so we query a few early-career searchTexts instead of listing all.
"""
from __future__ import annotations

import re

from .base import post_json, make_job, now_ts, is_early_career

SEARCH_TERMS = ["intern", "new grad", "university graduate", "early career"]


def _posted_ts(s, now):
    s = (s or "").lower()
    if "today" in s or "just posted" in s:
        return now
    if "yesterday" in s:
        return now - 86400
    m = re.search(r"(\d+)\+?\s*hour", s)
    if m:
        return now - int(m.group(1)) * 3600
    m = re.search(r"(\d+)\+?\s*day", s)
    if m:
        return now - int(m.group(1)) * 86400
    m = re.search(r"(\d+)\+?\s*month", s)
    if m:
        return now - int(m.group(1)) * 2592000
    return None


def fetch(cfg, early_career_only=True, max_pages=4):
    base = f"https://{cfg['tenant']}.{cfg['dc']}.myworkdayjobs.com"
    cxs = f"{base}/wday/cxs/{cfg['tenant']}/{cfg['site']}/jobs"
    pub = f"{base}/en-US/{cfg['site']}"
    now = now_ts()
    seen, jobs = set(), []
    for term in SEARCH_TERMS:
        for page in range(max_pages):
            try:
                d = post_json(cxs, {"appliedFacets": {}, "limit": 20,
                                    "offset": page * 20, "searchText": term})
            except Exception:  # noqa: BLE001
                break
            posts = d.get("jobPostings", [])
            if not posts:
                break
            for j in posts:
                path = j.get("externalPath") or ""
                if not path or path in seen:
                    continue
                seen.add(path)
                title = j.get("title") or ""
                if early_career_only and not is_early_career(title):
                    continue
                loc = j.get("locationsText") or ""
                jobs.append(make_job(
                    title=title,
                    company=cfg["name"],
                    url=pub + path,
                    locations=[loc] if loc and "location" not in loc.lower() else [],
                    source=f"workday:{cfg['tenant']}",
                    source_type="workday",
                    date_posted_ts=_posted_ts(j.get("postedOn"), now),
                ))
            if (page + 1) * 20 >= d.get("total", 0):
                break
    return jobs
