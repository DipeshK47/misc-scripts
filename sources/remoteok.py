"""RemoteOK public API (keyless) — newest ~100 remote jobs.

  GET https://remoteok.com/api   (requires a browser UA)
First list element is metadata/legal; the rest are jobs:
  {id, slug, position, company, apply_url|url, location, epoch (unix), tags[]}
Remote-global board; the us_only gate in scrape.py keeps US/remote rows.
"""
from __future__ import annotations

from .base import get_json, make_job, ats_should_keep

API = "https://remoteok.com/api"


def fetch(_token=None, mode="non_senior") -> list[dict]:
    data = get_json(API, timeout=25)
    jobs = []
    for j in data or []:
        title = j.get("position") or ""
        if not title or not ats_should_keep(title, mode):
            continue
        url = j.get("apply_url") or j.get("url") or (f"https://remoteok.com/remote-jobs/{j.get('id')}")
        tags = " ".join(j.get("tags") or [])
        jobs.append(make_job(
            title=title,
            company=j.get("company") or "",
            url=url,
            locations=[j.get("location") or "Remote"],
            source="remoteok:jobs",
            source_type="remoteok",
            date_posted_ts=j.get("epoch"),
            category_hint=tags,
        ))
    return jobs
