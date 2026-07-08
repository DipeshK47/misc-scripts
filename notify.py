#!/usr/bin/env python3
"""Push NEW jobs (state/new_this_run.json) to Discord and/or Slack webhooks.

Set one or both env vars (GitHub repo secrets):
  DISCORD_WEBHOOK_URL   SLACK_WEBHOOK_URL
No webhook set -> no-op (the run still succeeds).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
NEW = os.path.join(ROOT, "state", "new_this_run.json")
DASHBOARD = os.environ.get("DASHBOARD_URL", "")  # optional link in the message

CAT_LABEL = {
    "ai_ml": "AI/ML", "data_science": "Data Sci", "data_analytics": "Analytics",
    "research": "Research", "software": "Software", "webdev": "Web", "quant": "Quant",
}
SPONS = {"offers": "✅ sponsors", "no_sponsorship": "⚠️ no sponsorship",
         "citizen_required": "🇺🇸 citizen only", "unknown": ""}


def load_new():
    try:
        with open(NEW) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def when(j):
    ts = j.get("date_posted_ts") or j.get("first_seen_ts")
    if not ts:
        return ""
    mins = max(0, int(time.time()) - ts) // 60
    if mins < 60:
        return f"{mins}m ago"
    if mins < 1440:
        return f"{mins // 60}h ago"
    return f"{mins // 1440}d ago"


def line(j):
    cats = " ".join(CAT_LABEL.get(c, c) for c in j.get("categories", []))
    sp = SPONS.get(j.get("sponsorship", ""), "")
    loc = j.get("location") or ("Remote" if j.get("remote") else "")
    bits = [b for b in [loc, cats, sp, when(j)] if b]
    # .get() not subscript: one new job missing company/title/url must not
    # KeyError and abort alerts for every other job in the batch.
    title = j.get("title") or "(untitled)"
    company = j.get("company") or ""
    url = j.get("url") or "#"
    return f"**[{title}]({url})** — {company}\n{' · '.join(bits)}"


def send_discord(url, jobs):
    # Discord: <=10 embeds/msg; we use one compact embed listing up to ~15 jobs
    for i in range(0, len(jobs), 15):
        chunk = jobs[i:i + 15]
        desc = "\n\n".join(line(j) for j in chunk)
        if DASHBOARD:
            desc += f"\n\n[Open dashboard →]({DASHBOARD})"
        payload = {
            "username": "JobRadar",
            "embeds": [{
                "title": f"📡 {len(jobs)} new role{'s' if len(jobs) != 1 else ''} just posted",
                "description": desc[:4000],
                "color": 0x5b8cff,
                "footer": {"text": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")},
            }],
        }
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)))
            requests.post(url, json=payload, timeout=20)
        elif r.status_code >= 300:
            print(f"  discord error {r.status_code}: {r.text[:160]}")
        time.sleep(1)


def send_slack(url, jobs):
    text = f"📡 *{len(jobs)} new role{'s' if len(jobs) != 1 else ''} just posted*\n\n"
    text += "\n\n".join(
        f"<{j['url']}|*{j['title']}*> — {j['company']}\n"
        f"{' · '.join(b for b in [(j.get('location') or ''), ' '.join(CAT_LABEL.get(c, c) for c in j.get('categories', [])), when(j)] if b)}"
        for j in jobs[:40]
    )
    if DASHBOARD:
        text += f"\n\n<{DASHBOARD}|Open dashboard →>"
    r = requests.post(url, json={"text": text}, timeout=20)
    if r.status_code >= 300:
        print(f"  slack error {r.status_code}: {r.text[:160]}")


def main():
    jobs = load_new()
    if not jobs:
        print("notify: no new jobs this run.")
        return
    discord = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    slack = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not discord and not slack:
        print(f"notify: {len(jobs)} new jobs but no webhook configured (skipping).")
        return
    print(f"notify: sending {len(jobs)} new jobs...")
    if discord:
        send_discord(discord, jobs)
    if slack:
        send_slack(slack, jobs)
    print("notify: done.")


if __name__ == "__main__":
    main()
