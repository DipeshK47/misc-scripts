"""Workable public widget API (keyless).

  https://apply.workable.com/api/v1/widget/accounts/<account>?details=false
Returns {name, jobs:[{title, url, published_on (YYYY-MM-DD), created_at,
         city, state, country, telecommuting, locations[], ...}]}
"""
from __future__ import annotations

from .base import get_json, make_job, iso_to_ts, ats_should_keep

API = "https://apply.workable.com/api/v1/widget/accounts/{account}"


def fetch(account, mode="non_senior") -> list[dict]:
    data = get_json(API.format(account=account),
                    params={"details": "false"}, timeout=30)
    company = (data or {}).get("name") or account
    jobs = []
    for j in (data or {}).get("jobs", []):
        title = j.get("title") or ""
        if not ats_should_keep(title, mode):
            continue
        loc_str = ", ".join(p for p in (j.get("city"), j.get("state"), j.get("country")) if p)
        locs = [loc_str] if loc_str else []
        if j.get("telecommuting"):
            locs.append("Remote")
        jobs.append(make_job(
            title=title,
            company=company,
            url=j.get("url") or j.get("application_url") or "",
            locations=locs,
            source=f"workable:{account}",
            source_type="workable",
            date_posted_ts=iso_to_ts(j.get("published_on")) or iso_to_ts(j.get("created_at")),
        ))
    return jobs
