"""SmartRecruiters public postings API (keyless).

  https://api.smartrecruiters.com/v1/companies/<token>/postings?limit=100&offset=N
Returns {totalFound, content:[{id, name, releasedDate (ISO),
         location:{city,region,country,remote}, company:{identifier}, ...}]}
Public job page: https://jobs.smartrecruiters.com/<token>/<id>
"""
from __future__ import annotations

from .base import get_json, make_job, iso_to_ts, ats_should_keep

API = "https://api.smartrecruiters.com/v1/companies/{token}/postings"
PAGE = 100
MAX = 500  # ponytail: cap 5 pages/company; raise if a board ever exceeds it


def fetch(token, mode="non_senior") -> list[dict]:
    jobs, offset, total = [], 0, None
    while total is None or (offset < total and offset < MAX):
        data = get_json(API.format(token=token),
                        params={"limit": PAGE, "offset": offset}, timeout=30)
        total = (data or {}).get("totalFound", 0)
        rows = (data or {}).get("content", [])
        if not rows:
            break
        for j in rows:
            title = j.get("name") or ""
            if not ats_should_keep(title, mode):
                continue
            loc = j.get("location") or {}
            parts = [loc.get("city"), loc.get("region")]
            loc_str = ", ".join(p for p in parts if p)
            locs = [loc_str] if loc_str else []
            if loc.get("remote"):
                locs.append("Remote")
            jobs.append(make_job(
                title=title,
                company=(j.get("company") or {}).get("name") or token,
                url=f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}",
                locations=locs,
                country=loc.get("country"),
                source=f"smartrecruiters:{token}",
                source_type="smartrecruiters",
                date_posted_ts=iso_to_ts(j.get("releasedDate")),
            ))
        offset += PAGE
    return jobs
