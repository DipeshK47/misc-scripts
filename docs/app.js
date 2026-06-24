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

function loadPrefs() {
  const p = JSON.parse(localStorage.getItem(LS.prefs) || "{}");
  if (p.q != null) $("q").value = p.q;
  $("posted").value = p.posted || String(META.default_view_days || 7);
  $("sort").value = p.sort || "posted";
  $("role").value = p.role || "";
  $("spons").value = p.spons || "";
  $("t-new").checked = !!p.tnew;
  $("t-remote").checked = !!p.tremote;
  $("t-applied").checked = p.tapplied !== false;
  activeCats = new Set(p.cats || []);
}
function savePrefs() {
  localStorage.setItem(LS.prefs, JSON.stringify({
    q: $("q").value, posted: $("posted").value, sort: $("sort").value,
    role: $("role").value, spons: $("spons").value,
    tnew: $("t-new").checked, tremote: $("t-remote").checked, tapplied: $("t-applied").checked,
    cats: [...activeCats],
  }));
}

function buildChips() {
  const counts = {};
  JOBS.forEach((j) => (j.categories || []).forEach((c) => (counts[c] = (counts[c] || 0) + 1)));
  $("cat-chips").innerHTML = CATEGORIES
    .map(([k, label]) => `<span class="chip${activeCats.has(k) ? " on" : ""}" data-cat="${k}">${label}<span class="c">${counts[k] || 0}</span></span>`)
    .join("");
  $("cat-chips").querySelectorAll(".chip").forEach((el) =>
    el.addEventListener("click", () => {
      const c = el.dataset.cat;
      activeCats.has(c) ? activeCats.delete(c) : activeCats.add(c);
      el.classList.toggle("on");
      render();
    }));
}

function matches(j) {
  if ($("t-applied").checked && (applied.has(j.id) || hidden.has(j.id))) return false;
  if ($("t-new").checked && !j.is_new) return false;
  if ($("t-remote").checked && !j.remote) return false;
  if (activeCats.size && !(j.categories || []).some((c) => activeCats.has(c))) return false;
  const role = $("role").value;
  if (role && j.role_type !== role) return false;
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

function sortJobs(list) {
  const s = $("sort").value;
  if (s === "company") return list.sort((a, b) => a.company.localeCompare(b.company));
  if (s === "found") return list.sort((a, b) => (b.first_seen_ts || 0) - (a.first_seen_ts || 0));
  return list.sort((a, b) => (b.date_posted_ts || b.first_seen_ts || 0) - (a.date_posted_ts || a.first_seen_ts || 0));
}

const CAP = 500;
function jobRow(j) {
  const cats = (j.categories || []).map((c) => `<span class="t cat">${esc((CATEGORIES.find((x) => x[0] === c) || [, c])[1])}</span>`).join("");
  const ref = j.date_posted_ts || j.first_seen_ts;
  const fresh = ref && ref > Math.floor(Date.now() / 1000) - 86400;
  const when = j.date_posted_ts ? relTime(j.date_posted_ts) : "found " + relTime(j.first_seen_ts);
  const srcName = (j.sources && j.sources[0] || j.source || "").split(":").slice(-1)[0];
  const isApplied = applied.has(j.id);
  return `<div class="job${j.is_new ? " is-new" : ""}${isApplied ? " applied" : ""}" data-id="${j.id}">
    <div class="j-main">
      <div>
        ${j.is_new ? '<span class="pill-new">NEW</span> ' : ""}<a class="j-title" href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>
      </div>
      <div class="j-sub">
        <span class="j-company">${esc(j.company)}</span>
        ${j.location ? "· " + esc(j.location) : ""}
        ${j.remote ? '· <span style="color:var(--green)">Remote</span>' : ""}
      </div>
      <div class="j-tags">
        ${cats}
        ${j.role_type && ROLE_LABEL[j.role_type] ? `<span class="t role">${ROLE_LABEL[j.role_type]}</span>` : ""}
        <span class="badge ${j.sponsorship}">${SPONS_LABEL[j.sponsorship] || ""}</span>
        <span class="t src">${esc(srcName)}</span>
      </div>
    </div>
    <div class="j-right">
      <span class="j-when${fresh ? " fresh" : ""}">${when}</span>
      <div class="j-actions">
        <a class="btn apply" href="${esc(j.url)}" target="_blank" rel="noopener" data-act="apply">Apply ↗</a>
        <button class="btn ghost" data-act="hide" title="Dismiss">✕</button>
      </div>
    </div>
  </div>`;
}

function render() {
  savePrefs();
  const filtered = sortJobs(JOBS.filter(matches));
  const shown = filtered.slice(0, CAP);
  $("list").innerHTML = shown.map(jobRow).join("");
  $("empty").style.display = filtered.length ? "none" : "block";
  $("s-total").textContent = filtered.length;
  $("count-line").textContent =
    `${filtered.length} match${filtered.length === 1 ? "" : "es"}` +
    (filtered.length > CAP ? ` (showing first ${CAP})` : "") +
    ` · ${JOBS.length} tracked`;
  $("applied-count").textContent = `${applied.size} applied · ${hidden.size} dismissed`;

  $("list").querySelectorAll(".job").forEach((el) => {
    const id = el.dataset.id;
    el.querySelector('[data-act="apply"]').addEventListener("click", () => {
      applied.add(id); save(LS.applied, applied);
      el.classList.add("applied");
      if ($("t-applied").checked) setTimeout(render, 400);
      $("applied-count").textContent = `${applied.size} applied · ${hidden.size} dismissed`;
    });
    el.querySelector('[data-act="hide"]').addEventListener("click", () => {
      hidden.add(id); save(LS.hidden, hidden); render();
    });
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

async function boot() {
  try {
    const [jobs, meta] = await Promise.all([
      fetch("jobs.json?_=" + Date.now()).then((r) => r.json()),
      fetch("meta.json?_=" + Date.now()).then((r) => r.json()).catch(() => ({})),
    ]);
    JOBS = jobs; META = meta;
  } catch (e) {
    $("list").innerHTML = `<div class="empty">Couldn't load jobs.json — has the scraper run yet?</div>`;
    return;
  }
  $("s-new").textContent = META.new_this_run || 0;
  $("s-updated").textContent = META.generated_ts ? relTime(META.generated_ts) : "—";
  loadPrefs();
  buildChips();
  setupSources();
  render();

  let t;
  const deb = () => { clearTimeout(t); t = setTimeout(render, 150); };
  $("q").addEventListener("input", deb);
  ["posted", "sort", "role", "spons"].forEach((id) => $(id).addEventListener("change", render));
  ["t-new", "t-remote", "t-applied"].forEach((id) => $(id).addEventListener("change", render));
}

boot();
