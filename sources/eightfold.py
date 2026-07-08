"""Eightfold AI career sites — public JSON only on custom-domain deployments
(e.g. Netflix's explore.jobs.netflix.net); {slug}.eightfold.ai tenants are gated.

  GET {host}/api/apply/v2/jobs?domain={domain}&start=N&num=100&sort_by=timestamp
Returns {count, positions:[{name, canonicalPositionUrl, locations[], location,
         t_create (unix), t_update, ...}]}
cfg: {name, host, domain}
"""
from __future__ import annotations

from .base import get_json, make_job, ats_should_keep

PAGE = 100
MAX = 1000  # ponytail: sort order isn't reliably newest-first, so cover the whole board


def fetch(cfg, mode="non_senior") -> list[dict]:
    jobs, start, count = [], 0, None
    while count is None or (start < count and start < MAX):
        d = get_json(f"{cfg['host']}/api/apply/v2/jobs",
                     params={"domain": cfg["domain"], "start": start,
                             "num": PAGE, "sort_by": "timestamp"}, timeout=30)
        count = (d or {}).get("count", 0)
        rows = (d or {}).get("positions", [])
        if not rows:
            break
        for p in rows:
            title = p.get("name") or ""
            if not ats_should_keep(title, mode):
                continue
            locs = p.get("locations") or ([p["location"]] if p.get("location") else [])
            jobs.append(make_job(
                title=title,
                company=cfg["name"],
                url=p.get("canonicalPositionUrl") or f"{cfg['host']}/careers/job/{p.get('id')}",
                locations=locs,
                source=f"eightfold:{cfg['name'].lower()}",
                source_type="eightfold",
                date_posted_ts=p.get("t_create"),
                date_updated_ts=p.get("t_update"),
            ))
        start += PAGE
    return jobs
