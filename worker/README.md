# JobRadar "Scrape now" Worker

A tiny Cloudflare Worker that lets the **Scrape now** button on the dashboard
trigger an immediate fresh scrape (it dispatches the `update.yml` GitHub Action).
The GitHub token stays inside the Worker — never in the browser.

## Prereqs
- The `.github/workflows/update.yml` workflow must already exist on `main`
  (it has a `workflow_dispatch:` trigger).
- A free Cloudflare account + `wrangler` (`npm i -g wrangler`, or use `npx wrangler`).

## Deploy (≈3 min)
1. **Make a GitHub token** (fine-grained): github.com → Settings → Developer settings →
   Personal access tokens → Fine-grained → **Repository access: only `DipeshK47/misc-scripts`** →
   **Permissions → Actions: Read and write** → Generate. Copy it.

2. **Deploy the Worker:**
   ```bash
   cd worker
   npx wrangler login
   npx wrangler secret put GH_TOKEN      # paste the token from step 1
   npx wrangler deploy
   ```
   Wrangler prints a URL like `https://jobradar-scrape.<your-subdomain>.workers.dev`.

3. **Tell the dashboard about it:** open `docs/config.js` and set
   ```js
   window.JOBRADAR = { workerUrl: "https://jobradar-scrape.<your-subdomain>.workers.dev" };
   ```
   commit + push. The **Scrape now** button now works.

## Notes
- If your Pages URL isn't `https://dipeshk47.github.io`, add it to `ALLOWED_ORIGINS`
  in `src/index.js` and redeploy.
- The Worker debounces to one trigger per 30s per edge; GitHub's workflow
  `concurrency` group prevents overlapping runs.
- A click → scrape (~45s) → commit → Pages rebuild (~1 min). The button polls and
  refreshes the page automatically when the new data lands (~1–2 min total).
