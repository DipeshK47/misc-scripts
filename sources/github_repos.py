"""Curated GitHub repos that publish a machine-readable listings.json.

Confirmed schema (SimplifyJobs / vanshb03 family):
  id, company_name, company_url, title, locations[], url,
  active, is_visible, date_posted (unix s), date_updated (unix s),
  sponsorship, category, degrees[], terms[], source
"""
from __future__ import annotations

from .base import get_json, make_job


def fetch(repo_cfg) -> list[dict]:
    """repo_cfg: {name, url, default_role}. Returns normalized jobs."""
    name = repo_cfg["name"]
    url = repo_cfg["url"]
    default_role = repo_cfg.get("default_role")
    data = get_json(url, timeout=40)
    if not isinstance(data, list):
        return []

    jobs = []
    for row in data:
        if not isinstance(row, dict):
            continue
        # only live, visible postings
        if row.get("active") is False or row.get("is_visible") is False:
            continue
        title = row.get("title") or ""
        company = row.get("company_name") or ""
        apply_url = row.get("url") or row.get("company_url") or ""
        if not title or not apply_url:
            continue
        terms = row.get("terms") or []
        cat_field = row.get("category") or ""
        hint = " ".join([cat_field] + (terms if isinstance(terms, list) else []))
        jobs.append(make_job(
            title=title,
            company=company,
            url=apply_url,
            company_url=row.get("company_url"),
            locations=row.get("locations") or [],
            source=f"github:{name}",
            source_type="github_repo",
            date_posted_ts=row.get("date_posted"),
            date_updated_ts=row.get("date_updated"),
            sponsorship_raw=row.get("sponsorship"),
            role_default=default_role,
            category_hint=hint,
        ))
    return jobs
