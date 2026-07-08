"""The Muse public jobs API (keyless, ~500 req/hr/IP).

  https://www.themuse.com/api/public/jobs?category=X&level=Y&page=N
Returns {page_count, results:[{name, company:{name}, locations:[{name}],
         publication_date (ISO), levels, refs:{landing_page}}]}
Relevance-sorted (not by date) -> we fetch a few pages and let the recency
window in scrape.py drop stale rows.
"""
from __future__ import annotations

from .base import get_json, make_job, iso_to_ts

API = "https://www.themuse.com/api/public/jobs"
QUERIES = [
    ("Software Engineering", "Internship"),
    ("Software Engineering", "Entry Level"),
    ("Data and Analytics", "Internship"),
    ("Data and Analytics", "Entry Level"),
    ("Data Science", "Internship"),
    ("Data Science", "Entry Level"),
]
MAX_PAGES = 8  # ponytail: partial coverage; API has no date sort, deep pages are stale anyway
ROLE_OF = {"Internship": "internship", "Entry Level": "new_grad"}


def fetch(_token=None, mode="non_senior") -> list[dict]:
    jobs = []
    for category, level in QUERIES:
        page, page_count = 0, 1   # Muse pages are 0-indexed; page 0 is the top results
        while page < min(page_count, MAX_PAGES):
            data = get_json(API, params={"category": category, "level": level, "page": page},
                            timeout=30)
            page_count = (data or {}).get("page_count") or 0
            for j in (data or {}).get("results", []):
                title = j.get("name") or ""
                url = (j.get("refs") or {}).get("landing_page") or ""
                if not title or not url:
                    continue
                jobs.append(make_job(
                    title=title,
                    company=(j.get("company") or {}).get("name") or "",
                    url=url,
                    locations=[l.get("name") for l in (j.get("locations") or []) if l.get("name")],
                    source="muse:jobs",
                    source_type="muse",
                    date_posted_ts=iso_to_ts(j.get("publication_date")),
                    role_default=ROLE_OF.get(level),
                    category_hint=category.lower(),
                ))
            page += 1
    return jobs
