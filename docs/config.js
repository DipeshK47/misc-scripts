// JobRadar front-end config.
// After deploying the Cloudflare Worker (see /worker/README.md), paste its URL
// here so the "Scrape now" button can trigger an on-demand scrape. Leave empty
// to hide that button (the every-30-min auto-scrape + Refresh still work).
window.JOBRADAR = {
  workerUrl: "https://jobradar-scrape.itsdipeshk2003.workers.dev",
};
