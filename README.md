# 📡 JobRadar

A self-updating, single-page board of **fresh US new-grad / internship / research roles** in
AI/ML, data science, data analytics, software & web dev — **sorted by time posted** so you can
be among the first applicants.

It pulls from:
- **Curated GitHub trackers** (vanshb03, SimplifyJobs, cvrve, both-sides — the bot-maintained
  `listings.json` lists, which already aggregate LinkedIn/company postings with timestamps).
- **Company ATS boards** (Greenhouse / Lever / Ashby) — public JSON APIs from big tech *and*
  startups (OpenAI, Anthropic, Databricks, Stripe, Palantir, Perplexity, …), filtered to
  early-career roles only.

Every job is tagged with **category**, **role type** (intern / new-grad), and a **visa
sponsorship badge**. New roles since the last refresh get a **NEW** pill and (optionally) a
**Discord/Slack alert**.

> **On LinkedIn/Indeed scraping:** those sites actively block bots and ban IPs (against their
> ToS), so JobRadar deliberately leans on the legal, reliable sources above. The curated
> trackers already surface most LinkedIn-posted new-grad/intern roles.

---

## How it works

```
config/*.yaml ─▶ scrape.py ─▶ docs/jobs.json  ─▶ docs/index.html (the dashboard)
                     │         docs/meta.json
                     └───────▶ state/seen.json  (first-seen tracking → NEW + recency)
                               state/new_this_run.json ─▶ notify.py ─▶ Discord/Slack
```

A GitHub Action runs every 30 min: scrape → notify new jobs → commit refreshed data → GitHub
Pages serves the updated page. **No computer needs to stay on.**

---

## One-time setup (≈5 min)

1. **Create the repo & push** (from this folder):
   ```bash
   gh repo create jobradar --public --source=. --remote=origin --push
   # or: create an empty repo on github.com, then:
   #   git remote add origin https://github.com/<you>/jobradar.git && git push -u origin main
   ```

2. **Enable GitHub Pages**: repo **Settings → Pages → Source: Deploy from a branch →
   Branch: `main`, Folder: `/docs` → Save.**
   Your dashboard appears at `https://<you>.github.io/jobradar/`.

3. **Let the bot commit**: **Settings → Actions → General → Workflow permissions →
   "Read and write permissions" → Save.**

4. **Turn on alerts (Discord or Slack):**
   - Discord: Channel → Edit → Integrations → Webhooks → New Webhook → Copy URL.
   - Slack: create an *Incoming Webhook* and copy its URL.
   - Repo **Settings → Secrets and variables → Actions → New repository secret**:
     name `DISCORD_WEBHOOK_URL` (and/or `SLACK_WEBHOOK_URL`), paste the URL.
   - *(optional)* Add a **Variable** `DASHBOARD_URL` = your Pages URL, so alerts link back.

5. **Kick it off**: **Actions tab → "Update jobs" → Run workflow.** Done — it now self-updates.

---

## Run it locally

```bash
pip install -r requirements.txt
python scrape.py                 # writes docs/jobs.json + docs/meta.json
python -m http.server -d docs 8000   # open http://localhost:8000
# alerts locally (optional):
DISCORD_WEBHOOK_URL=... python notify.py
```

---

## Tuning it

| File | What to change |
|------|----------------|
| `config/companies.yaml` | Add/remove ATS company boards. Slug = the name in `boards.greenhouse.io/<x>`, `jobs.lever.co/<x>`, or `jobs.ashbyhq.com/<x>` (usually the lowercased company name). |
| `config/repos.yaml` | Add curated GitHub trackers. Use the raw URL of the repo's `.github/scripts/listings.json`. |
| `config/filters.yaml` | Recency windows, US-only toggle, which categories to keep, notification cap/categories. |
| `.github/workflows/update.yml` | Cron frequency (`*/30 * * * *`). GitHub may delay sub-15-min schedules under load. |

The dashboard itself has live filters (search, category chips, posted-within, role,
sponsorship, remote, "new only") and lets you mark jobs **Applied** or **dismiss** them — those
marks are saved in your browser's localStorage.

---

## Extending to more sources

The research that seeded this also documented exact public-API patterns (with verified live job
counts) for **Workday, SmartRecruiters, Recruitee, and Workable**, plus VC/startup boards. Adding
one is ~30 lines: drop a `sources/<platform>.py` with a `fetch()` that returns `make_job(...)`
dicts (copy `sources/greenhouse.py`), then list its tokens in a config file and register it in
`scrape.py`'s `collect()`. The normalization, dedup, NEW-tracking, filtering and dashboard all
work automatically for any new source.

Notable ATS slugs verified live (for quick expansion):
- **Greenhouse**: anthropic, databricks, stripe, scaleai, figma, samsara, airbnb, pinterest, robinhood, coinbase, gitlab, dropbox, discord, airtable
- **Lever**: palantir, spotify, matchgroup
- **Ashby**: openai, perplexity, elevenlabs, cohere, sierra, notion, ramp, cursor, writer, suno, modal, linear, runway
- **Workday** (needs `tenant`/`wdN`/`site`): nvidia · salesforce · adobe · redhat
