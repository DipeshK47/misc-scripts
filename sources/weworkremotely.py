"""We Work Remotely — public category RSS feeds (keyless).

  https://weworkremotely.com/categories/<cat>.rss
<item>: title ("Company: Role"), link, region, pubDate (RFC-822).
Remote-global; us_only gate keeps US/anywhere rows.
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from .base import get_text, make_job, ats_should_keep

FEEDS = [
    "remote-programming-jobs",
    "remote-devops-sysadmin-jobs",
    "remote-back-end-programming-jobs",
    "remote-front-end-programming-jobs",
    "remote-data-jobs",
]
BASE = "https://weworkremotely.com/categories/{cat}.rss"


def _ts(s):
    try:
        return int(parsedate_to_datetime(s).timestamp())
    except (TypeError, ValueError):
        return None


def fetch(_token=None, mode="non_senior") -> list[dict]:
    seen, jobs = set(), []
    for cat in FEEDS:
        try:
            root = ET.fromstring(get_text(BASE.format(cat=cat), timeout=25))
        except Exception:  # noqa: BLE001
            continue
        for it in root.iter("item"):
            link = (it.findtext("link") or "").strip()
            if not link or link in seen:
                continue
            seen.add(link)
            raw = (it.findtext("title") or "").strip()
            company, _, role = raw.partition(":")
            title = (role or raw).strip()
            if not title or not ats_should_keep(title, mode):
                continue
            region = (it.findtext("region") or "").strip()
            jobs.append(make_job(
                title=title,
                company=company.strip() if role else "",
                url=link,
                locations=[region or "Remote"],
                source="weworkremotely:rss",
                source_type="weworkremotely",
                date_posted_ts=_ts(it.findtext("pubDate")),
            ))
    return jobs
