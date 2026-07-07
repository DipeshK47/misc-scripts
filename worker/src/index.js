/**
 * JobRadar "Scrape now" trigger — Cloudflare Worker.
 *
 * The dashboard (static GitHub Pages) POSTs here; this Worker calls the GitHub
 * API to dispatch the `update.yml` workflow. The GitHub token lives ONLY here
 * (as a Worker secret), never in the browser. Requests are origin-checked and
 * debounced so the public URL can't be abused.
 *
 * Deploy: see ../README.md.  Set secret: `wrangler secret put GH_TOKEN`.
 */

const REPO = "DipeshK47/misc-scripts";
const WORKFLOW = "update.yml";
const ALLOWED_ORIGINS = [
  "https://dipeshk47.github.io",
  "http://localhost:8000",
  "http://localhost:8842",
];
const DEBOUNCE_MS = 30_000;

function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function dispatchScrape(env) {
  return fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "jobradar-scrape-worker",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
}

export default {
  // CF cron (wrangler.toml [triggers]) drives the scrape schedule — GitHub's
  // own free-tier cron only fires every ~2-4h.
  async scheduled(event, env, ctx) {
    const gh = await dispatchScrape(env);
    if (gh.status !== 204) {
      console.error(`cron dispatch failed: ${gh.status} ${(await gh.text()).slice(0, 300)}`);
    }
  },

  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const cors = corsHeaders(origin);

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const headers = { "Content-Type": "application/json", ...cors };
    const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers });

    if (request.method !== "POST") return json({ error: "POST only" }, 405);
    if (!ALLOWED_ORIGINS.includes(origin)) return json({ error: "forbidden origin" }, 403);
    if (!env.GH_TOKEN) return json({ error: "Worker missing GH_TOKEN secret" }, 500);

    // debounce (per-edge) so the public URL can't be hammered
    const cache = caches.default;
    const key = new Request("https://jobradar.internal/last-trigger");
    const last = await cache.match(key);
    if (last) {
      const elapsed = Date.now() - Number(await last.text());
      if (elapsed < DEBOUNCE_MS) {
        return json({ ok: false, throttled: true, retryAfterMs: DEBOUNCE_MS - elapsed }, 429);
      }
    }

    const gh = await dispatchScrape(env);

    if (gh.status === 204) {
      ctx.waitUntil(cache.put(key, new Response(String(Date.now()))));
      return json({ ok: true, message: "scrape triggered" });
    }
    const body = await gh.text();
    return json({ ok: false, status: gh.status, error: body.slice(0, 300) }, 502);
  },
};
