"""Recruitee public offers API (keyless).

  GET https://{slug}.recruitee.com/api/offers/
Returns {offers:[{title, careers_url, created_at, published_at?, city, country,
         remote?, status, ...}]}
"""
from __future__ import annotations

from .base import get_json, make_job, iso_to_ts, ats_should_keep

API = "https://{slug}.recruitee.com/api/offers/"


def fetch(slug, mode="non_senior") -> list[dict]:
    data = get_json(API.format(slug=slug), timeout=20)
    jobs = []
    for o in (data or {}).get("offers", []):
        title = o.get("title") or ""
        if not title or not ats_should_keep(title, mode):
            continue
        if o.get("status") and o["status"] != "published":
            continue
        loc = ", ".join(p for p in (o.get("city"), o.get("country")) if p)
        locs = [loc] if loc else []
        if o.get("remote"):
            locs.append("Remote")
        jobs.append(make_job(
            title=title,
            company=(data.get("company") or {}).get("name") if isinstance(data.get("company"), dict) else slug,
            url=o.get("careers_url") or "",
            locations=locs,
            source=f"recruitee:{slug}",
            source_type="recruitee",
            date_posted_ts=iso_to_ts(o.get("published_at")) or iso_to_ts(o.get("created_at")),
        ))
    return jobs
