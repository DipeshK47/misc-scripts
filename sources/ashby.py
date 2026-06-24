"""Ashby public job-board posting API.

  https://api.ashbyhq.com/posting-api/job-board/<org>
Returns {"jobs":[{id,title,department,team,employmentType,location,
secondaryLocations[],publishedAt(ISO),isListed,jobUrl,applyUrl,
address:{postalAddress:{addressRegion,addressCountry,addressLocality}}}]}
"""
from __future__ import annotations

from .base import get_json, make_job, iso_to_ts, ats_should_keep

API = "https://api.ashbyhq.com/posting-api/job-board/{org}"


def fetch(org, mode="non_senior") -> list[dict]:
    data = get_json(API.format(org=org), timeout=30)
    jobs = []
    for j in (data or {}).get("jobs", []):
        if j.get("isListed") is False:
            continue
        title = j.get("title") or ""
        if not ats_should_keep(title, mode):
            continue
        locs = [j.get("location")] + (j.get("secondaryLocations") or [])
        # secondaryLocations may be list of dicts with 'location'
        norm_locs = []
        for l in locs:
            if isinstance(l, dict):
                norm_locs.append(l.get("location") or l.get("locationName") or "")
            elif l:
                norm_locs.append(l)
        country = (((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry"))
        jobs.append(make_job(
            title=title,
            company=org,
            url=j.get("jobUrl") or j.get("applyUrl") or "",
            locations=[l for l in norm_locs if l],
            country=country,
            source=f"ashby:{org}",
            source_type="ashby",
            date_posted_ts=iso_to_ts(j.get("publishedAt")),
            category_hint=j.get("department") or j.get("team") or "",
        ))
    return jobs
