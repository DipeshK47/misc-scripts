"""Greenhouse public job-board API.

  https://boards-api.greenhouse.io/v1/boards/<token>/jobs
Returns {"jobs":[{id,title,absolute_url,location:{name},updated_at,first_published,...}]}
`first_published` is the true posting time (ISO); fall back to updated_at.
"""
from __future__ import annotations

from .base import get_json, make_job, iso_to_ts, ats_should_keep

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def fetch(token, mode="non_senior") -> list[dict]:
    # No content=true: we never use the HTML description, and it bloats the payload
    # ~14x (a big board is ~9MB vs ~0.7MB) -> OOM when many boards are in flight.
    data = get_json(API.format(token=token), timeout=30)
    jobs = []
    for j in (data or {}).get("jobs", []):
        title = j.get("title") or ""
        if not ats_should_keep(title, mode):
            continue
        loc = (j.get("location") or {}).get("name") or ""
        # Use ONLY first_published as the post date. updated_at changes whenever a
        # recruiter edits the posting, so it would make old jobs look brand new.
        # If first_published is missing, leave posted empty -> UI shows "found <when>".
        posted = iso_to_ts(j.get("first_published"))
        jobs.append(make_job(
            title=title,
            company=token,
            url=j.get("absolute_url") or "",
            locations=[loc] if loc else [],
            source=f"greenhouse:{token}",
            source_type="greenhouse",
            date_posted_ts=posted,
            date_updated_ts=iso_to_ts(j.get("updated_at")),
        ))
    return jobs
