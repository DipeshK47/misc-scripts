"use strict";

const CATEGORIES = [
  ["ai_ml", "AI / ML"],
  ["data_science", "Data Science"],
  ["data_analytics", "Data Analytics"],
  ["research", "Research"],
  ["software", "Software"],
  ["webdev", "Web Dev"],
  ["quant", "Quant"],
];
// source-prefix -> chip label; a job matches if ANY of its sources has the prefix
const SOURCES = [
  ["greenhouse", "Greenhouse"],
  ["lever", "Lever"],
  ["ashby", "Ashby"],
  ["workday", "Workday"],
  ["github", "GitHub lists"],
];
const SPONS_LABEL = {
  offers: "Sponsors",
  no_sponsorship: "No sponsorship",
  citizen_required: "Citizen only",
  unknown: "Sponsorship N/A",
};
const ROLE_LABEL = { internship: "Internship", new_grad: "New grad", early_career: "Early career", unknown: "" };

const LS = {
  applied: "jr_applied",
  hidden: "jr_hidden",
  prefs: "jr_prefs",
};

let JOBS = [];
let META = {};
let applied = new Set(JSON.parse(localStorage.getItem(LS.applied) || "[]"));
let hidden = new Set(JSON.parse(localStorage.getItem(LS.hidden) || "[]"));
let activeCats = new Set();
let activeSrcs = new Set();     // source prefixes ("greenhouse", "github", …)
let roleSel = "";               // "", "internship", "new_grad" (segmented control)
let booting = true;             // first render gets the staggered reveal

const $ = (id) => document.getElementById(id);
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function save(key, set) { localStorage.setItem(key, JSON.stringify([...set])); }

function relTime(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.floor(Date.now() / 1000) - ts);
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  const d = Math.floor(s / 86400);
  if (d < 30) return d + "d ago";
  return Math.floor(d / 30) + "mo ago";
}
function absDate(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function loadPrefs() {
  const p = JSON.parse(localStorage.getItem(LS.prefs) || "{}");
  if (p.q != null) $("q").value = p.q;
  $("posted").value = p.posted || String(META.default_view_days || 7);
  $("sort").value = p.sort || "posted";
  $("loc").value = p.loc || "";
  roleSel = p.role || "";
  $("level").value = p.level || "";
  $("spons").value = p.spons || "";
  $("t-new").checked = !!p.tnew;
  $("t-remote").checked = !!p.tremote;
  $("t-hide-applied").checked = !!p.thideApplied;
  $("t-show-dismissed").checked = !!p.tshowDismissed;
  activeCats = new Set(p.cats || []);
  activeSrcs = new Set(p.srcs || []);
}
function savePrefs() {
  localStorage.setItem(LS.prefs, JSON.stringify({
    q: $("q").value, posted: $("posted").value, sort: $("sort").value, loc: $("loc").value,
    role: roleSel, level: $("level").value, spons: $("spons").value,
    tnew: $("t-new").checked, tremote: $("t-remote").checked,
    thideApplied: $("t-hide-applied").checked, tshowDismissed: $("t-show-dismissed").checked,
    cats: [...activeCats], srcs: [...activeSrcs],
  }));
}

function buildChipGroup(elId, defs, activeSet) {
  $(elId).innerHTML = defs
    .map(([k, label]) => `<span class="chip${activeSet.has(k) ? " on" : ""}" data-key="${k}" role="button" tabindex="0">${label}<span class="c">0</span></span>`)
    .join("");
  $(elId).querySelectorAll(".chip").forEach((el) => {
    const toggle = () => {
      const k = el.dataset.key;
      activeSet.has(k) ? activeSet.delete(k) : activeSet.add(k);
      el.classList.toggle("on");
      render();
    };
    el.addEventListener("click", toggle);
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
  });
}
// chip counts reflect the CURRENT filters (minus the chip group itself), so they
// always tell you how many you'd actually get.
function updateChipCounts(elId, counts) {
  $(elId).querySelectorAll(".chip").forEach((el) => {
    el.querySelector(".c").textContent = counts[el.dataset.key] || 0;
  });
}

function srcPrefixes(j) {
  return (j.sources && j.sources.length ? j.sources : [j.source || ""]).map((s) => String(s).split(":")[0]);
}

/* segmented role control */
function buildSeg() {
  const btns = [...document.querySelectorAll("#role-seg .seg-btn")];
  const sync = () => {
    btns.forEach((b, i) => {
      const on = (b.dataset.role || "") === roleSel;
      b.setAttribute("aria-pressed", String(on));
      if (on) $("seg-thumb").style.transform = `translateX(${i * 100}%)`;
    });
  };
  btns.forEach((b) => b.addEventListener("click", () => { roleSel = b.dataset.role || ""; sync(); render(); }));
  sync();
}

function inRegion(j, region) {
  const L = (j.location || "").toLowerCase();
  if (region === "remote") return !!j.remote;
  const nj = /\bnj\b|new jersey|jersey city|newark|hoboken|princeton|edison|trenton|parsippany|secaucus|paramus|morristown|piscataway/.test(L);
  const nyc = /\b(new york|nyc|manhattan|brooklyn|queens|bronx|staten island|long island city)\b/.test(L);
  const nystate = /\bny\b|new york/.test(L) || nyc;
  if (region === "nyc") return nyc;
  if (region === "nj") return nj;
  if (region === "nystate") return nystate;
  if (region === "metro") return nyc || nj || nystate;
  return true;
}

// every filter EXCEPT the category chips (so chip counts can be computed)
function passNonCat(j) {
  if (hidden.has(j.id) && !$("t-show-dismissed").checked) return false;
  if (applied.has(j.id) && $("t-hide-applied").checked) return false;
  if ($("t-new").checked && !j.is_new) return false;
  if ($("t-remote").checked && !j.remote) return false;
  const loc = $("loc").value;
  if (loc && !inRegion(j, loc)) return false;
  if (roleSel && j.role_type !== roleSel) return false;
  const level = $("level").value;
  if (level && j.level !== level) return false;
  const sp = $("spons").value;
  if (sp && j.sponsorship !== sp) return false;
  const days = parseInt($("posted").value, 10);
  if (days < 9999) {
    const ref = j.date_posted_ts || j.first_seen_ts;
    if (!ref || ref < Math.floor(Date.now() / 1000) - days * 86400) return false;
  }
  const q = $("q").value.trim().toLowerCase();
  if (q) {
    const hay = (j.title + " " + j.company + " " + j.location + " " + (j.categories || []).join(" ")).toLowerCase();
    if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
  }
  return true;
}
const catPass = (j) => !activeCats.size || (j.categories || []).some((c) => activeCats.has(c));
const srcPass = (j) => !activeSrcs.size || srcPrefixes(j).some((p) => activeSrcs.has(p));

function sortJobs(list) {
  const s = $("sort").value;
  if (s === "company") return list.sort((a, b) => a.company.localeCompare(b.company));
  if (s === "found") return list.sort((a, b) => (b.first_seen_ts || 0) - (a.first_seen_ts || 0));
  return list.sort((a, b) => (b.date_posted_ts || b.first_seen_ts || 0) - (a.date_posted_ts || a.first_seen_ts || 0));
}

const CAP = 500;
function jobRow(j, i) {
  const stagger = booting ? ` reveal" style="--i:${Math.min(i || 0, 12)}` : "";
  const cats = (j.categories || []).map((c) => `<span class="t cat">${esc((CATEGORIES.find((x) => x[0] === c) || [, c])[1])}</span>`).join("");
  const srcName = (j.sources && j.sources[0] || j.source || "").split(":").slice(-1)[0];
  const ref = j.date_posted_ts || j.first_seen_ts;
  const fresh = ref && ref > Math.floor(Date.now() / 1000) - 86400;
  let when, whenTitle;
  if (j.date_posted_ts) {
    when = `${absDate(j.date_posted_ts)} · ${relTime(j.date_posted_ts)}`;
    whenTitle = `First listed ${new Date(j.date_posted_ts * 1000).toLocaleString()} (via ${srcName}). A company's own page may show a different internal posting date.`;
  } else {
    when = `found ${relTime(j.first_seen_ts)}`;
    whenTitle = `No post-date from the source; JobRadar first saw this ${relTime(j.first_seen_ts)} (via ${srcName}).`;
  }
  const isApplied = applied.has(j.id);
  const isHidden = hidden.has(j.id);
  return `<div class="job${j.is_new ? " is-new" : ""}${isApplied ? " applied" : ""}${stagger}" data-id="${j.id}">
    <div class="j-main">
      <div>
        ${j.is_new ? '<span class="pill-new">NEW</span> ' : ""}<a class="j-title" href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>
        ${isApplied ? ' <span class="pill-applied" data-act="unapply" title="Click to unmark">✓ Applied</span>' : ""}
      </div>
      <div class="j-sub">
        <span class="j-company">${esc(j.company)}</span>
        ${j.location ? "· " + esc(j.location) : ""}
        ${j.remote ? '· <span class="j-remote">Remote</span>' : ""}
      </div>
      <div class="j-tags">
        ${cats}
        ${j.role_type && ROLE_LABEL[j.role_type] ? `<span class="t role">${ROLE_LABEL[j.role_type]}</span>` : (j.level === "mid" ? '<span class="t role">Entry–mid</span>' : "")}
        <span class="badge ${j.sponsorship}">${SPONS_LABEL[j.sponsorship] || ""}</span>
        <span class="t src">${esc(srcName)}</span>
      </div>
    </div>
    <div class="j-right">
      <span class="j-when${fresh ? " fresh" : ""}" title="${esc(whenTitle)}">${when}</span>
      <div class="j-actions">
        <a class="btn apply" href="${esc(j.url)}" target="_blank" rel="noopener" data-act="apply">Apply ↗</a>
        ${isHidden
          ? '<button class="btn ghost" data-act="restore" title="Restore">↩</button>'
          : '<button class="btn ghost" data-act="hide" title="Dismiss">✕</button>'}
      </div>
    </div>
  </div>`;
}

function render() {
  savePrefs();
  // base = everything matching the current filters EXCEPT the two chip groups.
  const base = JOBS.filter(passNonCat);
  const catCounts = {}, srcCounts = {};
  base.forEach((j) => {
    if (srcPass(j)) (j.categories || []).forEach((c) => (catCounts[c] = (catCounts[c] || 0) + 1));
    if (catPass(j)) new Set(srcPrefixes(j)).forEach((p) => (srcCounts[p] = (srcCounts[p] || 0) + 1));
  });
  updateChipCounts("cat-chips", catCounts);
  updateChipCounts("src-chips", srcCounts);
  const filtered = sortJobs(base.filter((j) => catPass(j) && srcPass(j)));
  const shown = filtered.slice(0, CAP);
  $("list").innerHTML = shown.map(jobRow).join("");
  $("empty").style.display = filtered.length ? "none" : "block";
  $("s-total").textContent = filtered.length;
  $("s-new").textContent = filtered.filter((j) => j.is_new).length;   // NEW in current view
  $("count-line").textContent =
    `${filtered.length} match${filtered.length === 1 ? "" : "es"}` +
    (filtered.length > CAP ? ` (showing first ${CAP})` : "") +
    ` · ${JOBS.length} tracked`;
  $("applied-count").textContent = `${applied.size} applied · ${hidden.size} dismissed`;

  const counts = () => { $("applied-count").textContent = `${applied.size} applied · ${hidden.size} dismissed`; };
  $("list").querySelectorAll(".job").forEach((el) => {
    const id = el.dataset.id;
    const unapply = (e) => { if (e) { e.preventDefault(); e.stopPropagation(); } applied.delete(id); save(LS.applied, applied); render(); };
    // Apply: follow the link (default <a>) AND mark applied — but never auto-hide
    // unless the user opted into "Hide applied".
    el.querySelector('[data-act="apply"]').addEventListener("click", () => {
      applied.add(id); save(LS.applied, applied);
      el.classList.add("applied");
      if (!el.querySelector(".pill-applied")) {
        const t = el.querySelector(".j-title");
        t.insertAdjacentHTML("afterend", ' <span class="pill-applied" data-act="unapply" title="Click to unmark">✓ Applied</span>');
        el.querySelector(".pill-applied").addEventListener("click", unapply);
      }
      counts();
      if ($("t-hide-applied").checked) setTimeout(render, 500);
    });
    const pa = el.querySelector('[data-act="unapply"]');
    if (pa) pa.addEventListener("click", unapply);
    const hideBtn = el.querySelector('[data-act="hide"]');
    if (hideBtn) hideBtn.addEventListener("click", () => { hidden.add(id); save(LS.hidden, hidden); render(); });
    const restoreBtn = el.querySelector('[data-act="restore"]');
    if (restoreBtn) restoreBtn.addEventListener("click", () => { hidden.delete(id); save(LS.hidden, hidden); render(); });
  });
}

function setupSources() {
  const s = META.sources || [];
  const bad = s.filter((x) => !x.ok);
  $("src-line").innerHTML =
    `Pulling from <b>${s.length}</b> sources · <b>${s.filter((x) => x.ok).length}</b> live` +
    (META.first_run ? " · <i>baseline run (NEW flags start next refresh)</i>" : "");
  $("src-health").innerHTML = s
    .map((x) => `<span class="${x.ok ? "" : "bad"}" title="${esc(x.error || "")}">${esc(x.source)}${x.ok ? " " + x.count : " ✕"}</span>`)
    .join("");
}

async function loadData() {
  const [jobs, meta] = await Promise.all([
    fetch("jobs.json?_=" + Date.now()).then((r) => r.json()),
    fetch("meta.json?_=" + Date.now()).then((r) => r.json()).catch(() => ({})),
  ]);
  JOBS = jobs; META = meta;
  $("s-updated").textContent = META.generated_ts ? relTime(META.generated_ts) : "—";
}

// Re-pull the latest auto-scraped data file (the cron updates it ~every 30 min).
// A static page can't run the Python scraper itself; this fetches the freshest
// committed jobs.json. To force a brand-new scrape, run the GitHub Action.
async function refresh() {
  const btn = $("refresh");
  if (btn.classList.contains("spin")) return;
  btn.classList.add("spin");
  try {
    await loadData();
    setupSources();
    render();
  } catch (e) { /* keep showing current data */ }
  setTimeout(() => btn.classList.remove("spin"), 700);
}

function setStatus(msg) { $("scrape-status").textContent = msg || ""; }

// Trigger a brand-new scrape via the Cloudflare Worker, then poll meta.json
// until the freshly-committed data shows up (~1–2 min: scrape + Pages rebuild).
async function scrapeNow() {
  const cfg = window.JOBRADAR || {};
  const btn = $("scrape-now");
  if (!cfg.workerUrl) {
    setStatus("Set up the Worker first (see /worker) — then add its URL to config.js.");
    return;
  }
  if (btn.dataset.busy) return;
  btn.dataset.busy = "1"; btn.classList.add("spin");
  const before = META.generated_ts || 0;
  setStatus("Triggering a fresh scrape…");
  const done = () => { btn.dataset.busy = ""; btn.classList.remove("spin"); };
  try {
    const r = await fetch(cfg.workerUrl, { method: "POST" });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.ok === false) {
      setStatus(j.throttled ? "Just scraped — try again in a few seconds." : "Couldn't trigger scrape.");
      done(); return;
    }
  } catch (e) { setStatus("Worker unreachable — check config.js / deploy."); done(); return; }

  setStatus("Scraping… new jobs in ~1–2 min");
  let tries = 0;
  const iv = setInterval(async () => {
    tries++;
    try {
      const m = await fetch("meta.json?_=" + Date.now()).then((r) => r.json());
      if ((m.generated_ts || 0) > before) {
        clearInterval(iv);
        await loadData(); setupSources(); render();
        setStatus("Updated just now ✓"); done();
        setTimeout(() => setStatus(""), 5000);
        return;
      }
    } catch (e) { /* keep polling */ }
    if (tries >= 30) {                       // ~5 min
      clearInterval(iv);
      setStatus("Still scraping — hit Refresh shortly."); done();
    }
  }, 10000);
}

// one-time count-up on the header stats (skipped under reduced motion)
function countUpStats() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  ["s-total", "s-new"].forEach((id) => {
    const el = $(id), end = parseInt(el.textContent, 10);
    if (!end) return;
    const t0 = performance.now(), dur = 600;
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

async function boot() {
  try {
    await loadData();
  } catch (e) {
    $("list").innerHTML = `<div class="empty">Couldn't load jobs.json — has the scraper run yet?</div>`;
    return;
  }
  loadPrefs();
  buildChipGroup("cat-chips", CATEGORIES, activeCats);
  buildChipGroup("src-chips", SOURCES, activeSrcs);
  buildSeg();
  setupSources();
  render();
  booting = false;          // later renders skip the entrance stagger
  countUpStats();

  let t;
  const deb = () => { clearTimeout(t); t = setTimeout(render, 150); };
  $("q").addEventListener("input", deb);
  ["posted", "sort", "loc", "level", "spons"].forEach((id) => $(id).addEventListener("change", render));
  ["t-new", "t-remote", "t-hide-applied", "t-show-dismissed"].forEach((id) => $(id).addEventListener("change", render));
  $("refresh").addEventListener("click", refresh);
  const sn = $("scrape-now");
  if ((window.JOBRADAR || {}).workerUrl) sn.style.display = "";
  sn.addEventListener("click", scrapeNow);
}

boot();
