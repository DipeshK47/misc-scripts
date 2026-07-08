"""Direct company careers APIs for giants that aren't on a public ATS.

amazon    GET https://www.amazon.jobs/en/search.json?base_query={q}&sort=recent
          jobs[]: title, job_path, posted_date ("July 1, 2026"), normalized_location
microsoft GET https://gcsservices.careers.microsoft.com/search/api/v1/search
          (experimental: unreachable from some networks; health report will tell)
"""
from __future__ import annotations

from datetime import datetime, timezone

from .base import get_json, make_job, ats_should_keep, iso_to_ts

TERMS = ["intern", "new grad", "university graduate", "early career"]


def _us_date(s):
    try:
        return int(datetime.strptime(" ".join((s or "").split()), "%B %d, %Y")
                   .replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def amazon(mode="non_senior") -> list[dict]:
    seen, jobs = set(), []
    for term in TERMS:
        d = get_json("https://www.amazon.jobs/en/search.json",
                     params={"base_query": term, "result_limit": 100,
                             "sort": "recent", "offset": 0}, timeout=30)
        for j in (d or {}).get("jobs", []):
            path = j.get("job_path") or ""
            if not path or path in seen:
                continue
            seen.add(path)
            title = j.get("title") or ""
            if not ats_should_keep(title, mode):
                continue
            jobs.append(make_job(
                title=title,
                company="Amazon",
                url="https://www.amazon.jobs" + path,
                locations=[j.get("normalized_location") or j.get("location") or ""],
                source="direct:amazon",
                source_type="direct",
                date_posted_ts=_us_date(j.get("posted_date")),
            ))
    return jobs


def microsoft(mode="non_senior") -> list[dict]:
    seen, jobs = set(), []
    for term in TERMS:
        d = get_json("https://gcsservices.careers.microsoft.com/search/api/v1/search",
                     params={"q": term, "pg": 1, "pgSz": 100, "o": "Recent"}, timeout=30)
        for j in (((d or {}).get("operationResult") or {}).get("result") or {}).get("jobs", []):
            jid = j.get("jobId") or ""
            if not jid or jid in seen:
                continue
            seen.add(jid)
            title = j.get("title") or ""
            if not ats_should_keep(title, mode):
                continue
            props = j.get("properties") or {}
            jobs.append(make_job(
                title=title,
                company="Microsoft",
                url=f"https://jobs.careers.microsoft.com/global/en/job/{jid}",
                locations=props.get("locations") or [],
                source="direct:microsoft",
                source_type="direct",
                date_posted_ts=iso_to_ts(j.get("postingDate")),
            ))
    return jobs


FETCHERS = {"amazon": amazon, "microsoft": microsoft}


def fetch(name, mode="non_senior") -> list[dict]:
    return FETCHERS[name](mode)
