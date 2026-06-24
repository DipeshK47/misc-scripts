"""Lever public postings API.

  https://api.lever.co/v0/postings/<company>?mode=json
Returns a JSON array of {id,text,categories:{location,team,commitment},
hostedUrl,applyUrl,createdAt(ms epoch),...}
"""
from __future__ import annotations

from .base import get_json, make_job, ats_should_keep

API = "https://api.lever.co/v0/postings/{company}"


def fetch(company, mode="non_senior") -> list[dict]:
    data = get_json(API.format(company=company), params={"mode": "json"}, timeout=30)
    if not isinstance(data, list):
        return []
    jobs = []
    for j in data:
        title = j.get("text") or ""
        if not ats_should_keep(title, mode):
            continue
        cats = j.get("categories") or {}
        loc = cats.get("location") or ""
        created = j.get("createdAt")
        created_s = int(created / 1000) if created else None
        jobs.append(make_job(
            title=title,
            company=company,
            url=j.get("hostedUrl") or j.get("applyUrl") or "",
            locations=[loc] if loc else [],
            source=f"lever:{company}",
            source_type="lever",
            date_posted_ts=created_s,
            category_hint=cats.get("team") or "",
        ))
    return jobs
