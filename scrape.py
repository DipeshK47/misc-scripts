#!/usr/bin/env python3
"""JobRadar aggregator.

Pulls early-career US tech jobs from curated GitHub repos + company ATS boards,
normalizes/dedups them, tracks first-seen time (for "NEW" + recency), and writes:
  docs/jobs.json          -> the dashboard data
  docs/meta.json          -> run stats / source health
  state/seen.json         -> persistent first-seen tracking
  state/new_this_run.json -> new jobs for the notifier
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import yaml

from sources import github_repos, greenhouse, lever, ashby
from sources.base import now_ts, now_iso, is_early_career, is_senior

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(ROOT, "config")
DOCS = os.path.join(ROOT, "docs")
STATE = os.path.join(ROOT, "state")
DAY = 86400


def load_yaml(name):
    with open(os.path.join(CFG, name)) as f:
        return yaml.safe_load(f) or {}


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


# --------------------------------------------------------------------------- #
# Collect from every source (in parallel, isolated failures)
# --------------------------------------------------------------------------- #
def collect(repos_cfg, companies_cfg, early_only):
    tasks = []  # (label, callable)
    for repo in repos_cfg.get("repos", []):
        tasks.append((f"github:{repo['name']}", lambda r=repo: github_repos.fetch(r)))
    for tok in companies_cfg.get("greenhouse", []) or []:
        tasks.append((f"greenhouse:{tok}", lambda t=tok: greenhouse.fetch(t, early_only)))
    for c in companies_cfg.get("lever", []) or []:
        tasks.append((f"lever:{c}", lambda x=c: lever.fetch(x, early_only)))
    for o in companies_cfg.get("ashby", []) or []:
        tasks.append((f"ashby:{o}", lambda x=o: ashby.fetch(x, early_only)))

    jobs, health = [], []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(fn): label for label, fn in tasks}
        for fut in as_completed(futs):
            label = futs[fut]
            try:
                got = fut.result()
                jobs.extend(got)
                health.append({"source": label, "ok": True, "count": len(got)})
                print(f"  ok   {label:42s} {len(got):5d}")
            except Exception as e:  # noqa: BLE001
                health.append({"source": label, "ok": False, "count": 0, "error": str(e)[:160]})
                print(f"  FAIL {label:42s} {str(e)[:80]}")
    return jobs, health


# --------------------------------------------------------------------------- #
# Filter + dedup
# --------------------------------------------------------------------------- #
def keep(job, filt, now):
    if not job.get("title") or not job.get("url"):
        return False
    if filt.get("us_only", True) and not job.get("is_us", True):
        return False
    targets = set(filt.get("target_categories", []))
    if targets and not (set(job.get("categories", [])) & targets):
        return False
    # recency: posted within window OR (no date -> let seen-window decide later)
    dp = job.get("date_posted_ts")
    if dp is not None:
        if dp > now + DAY:          # bogus future timestamp -> ignore the date
            job["date_posted_ts"] = None
            job["date_posted"] = None
        elif dp < now - filt.get("window_days_posted", 45) * DAY:
            return False
    return True


def dedup(jobs):
    """Merge by stable id; keep earliest post date, union categories/sources."""
    by_id = {}
    for j in jobs:
        ex = by_id.get(j["id"])
        if not ex:
            by_id[j["id"]] = j
            j["sources"] = [j["source"]]
            continue
        ex["sources"] = sorted(set(ex.get("sources", [ex["source"]]) + [j["source"]]))
        ex["categories"] = sorted(set(ex.get("categories", []) + j.get("categories", [])))
        # prefer a real post date, earliest wins
        for key in ("date_posted_ts",):
            a, b = ex.get(key), j.get(key)
            if b and (not a or b < a):
                ex["date_posted_ts"] = b
                ex["date_posted"] = j.get("date_posted")
        # prefer a known sponsorship over unknown
        if ex.get("sponsorship") == "unknown" and j.get("sponsorship") != "unknown":
            ex["sponsorship"] = j["sponsorship"]
    return list(by_id.values())


# --------------------------------------------------------------------------- #
# First-seen / NEW tracking
# --------------------------------------------------------------------------- #
def apply_seen(jobs, filt, now):
    seen_path = os.path.join(STATE, "seen.json")
    first_run = not os.path.exists(seen_path)
    seen = load_json(seen_path, {})

    new_jobs = []
    for j in jobs:
        rec = seen.get(j["id"])
        if rec:
            j["first_seen_ts"] = rec.get("first_seen_ts", now)
            j["is_new"] = False
        else:
            j["first_seen_ts"] = now
            j["is_new"] = not first_run     # don't flag the whole world on run #1
            if j["is_new"]:
                new_jobs.append(j)
        j["first_seen"] = datetime.fromtimestamp(j["first_seen_ts"], tz=timezone.utc).isoformat()
        seen[j["id"]] = {"first_seen_ts": j["first_seen_ts"], "last_seen_ts": now}

    # second recency gate: drop undated jobs we first saw long ago
    win_seen = filt.get("window_days_seen", 14) * DAY
    kept = [j for j in jobs
            if j.get("date_posted_ts") is not None or j["first_seen_ts"] >= now - win_seen]
    kept_ids = {j["id"] for j in kept}

    # prune state
    cutoff = now - filt.get("seen_retention_days", 120) * DAY
    seen = {k: v for k, v in seen.items() if v.get("last_seen_ts", now) >= cutoff}
    save_json(seen_path, seen)

    # notify-eligible new jobs (must survive recency gate + match notify categories)
    ncats = set(filt.get("notify", {}).get("categories", []))
    cap = filt.get("notify", {}).get("max_per_run", 25)
    elig = [] if first_run else [
        j for j in new_jobs
        if j["id"] in kept_ids and (not ncats or set(j.get("categories", [])) & ncats)
    ]
    elig.sort(key=lambda j: (j.get("date_posted_ts") or j["first_seen_ts"]), reverse=True)
    save_json(os.path.join(STATE, "new_this_run.json"), elig[:cap])

    return kept, len(new_jobs), first_run


# --------------------------------------------------------------------------- #
def main():
    repos_cfg = load_yaml("repos.yaml")
    companies_cfg = load_yaml("companies.yaml")
    filt = load_yaml("filters.yaml")
    now = now_ts()

    print("== collecting ==")
    raw, health = collect(repos_cfg, companies_cfg,
                          filt.get("ats_early_career_only", True))
    print(f"collected {len(raw)} raw rows from {len(health)} sources")

    filtered = [j for j in raw if keep(j, filt, now)]
    deduped = dedup(filtered)
    kept, n_new, first_run = apply_seen(deduped, filt, now)

    # sort: newest posted first; undated fall back to first-seen
    kept.sort(key=lambda j: (j.get("date_posted_ts") or j["first_seen_ts"]), reverse=True)

    # stats
    by_cat, by_src, by_role = {}, {}, {}
    for j in kept:
        for c in j.get("categories", []) or ["uncategorized"]:
            by_cat[c] = by_cat.get(c, 0) + 1
        by_src[j["source_type"]] = by_src.get(j["source_type"], 0) + 1
        by_role[j["role_type"]] = by_role.get(j["role_type"], 0) + 1

    save_json(os.path.join(DOCS, "jobs.json"), kept)
    save_json(os.path.join(DOCS, "meta.json"), {
        "generated_at": now_iso(),
        "generated_ts": now,
        "total": len(kept),
        "new_this_run": 0 if first_run else n_new,
        "first_run": first_run,
        "default_view_days": filt.get("default_view_days", 7),
        "by_category": by_cat,
        "by_source": by_src,
        "by_role": by_role,
        "sources": sorted(health, key=lambda h: (not h["ok"], h["source"])),
    })

    print(f"== done == kept {len(kept)} jobs | {n_new} new "
          f"{'(first run, not flagged)' if first_run else ''}")
    print(f"   categories: {by_cat}")
    print(f"   sources ok: {sum(h['ok'] for h in health)}/{len(health)}")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
