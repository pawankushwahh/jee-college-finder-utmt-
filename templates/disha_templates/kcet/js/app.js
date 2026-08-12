"use strict";

/* ═══════════════════════════════════════════════════════════════
   Disha — KCET (standalone SPA, NO shared JEE/COMEDK code)

   View IDs (each step is its own <section>):
     view-welcome  view-step-0  view-step-1  view-step-2  view-step-3
     view-step-4   view-loading  view-results  view-error

   Flow: rank -> category -> branch preferences -> interest -> review

   API:  GET  /api/kcet/meta
         POST /api/kcet/recommend
   ═══════════════════════════════════════════════════════════════ */

// ── GOALS (icons + copy; labels are overridden from /meta at load time) ──

const GOALS = [
  { id: "coding",       name: "CS / Software / AI",           desc: "Computer Science, IT, AI/Data Science" },
  { id: "core",         name: "Core Engineering",              desc: "Mechanical, Civil, Electrical, Chemical" },
  { id: "research",     name: "Research / Higher Studies",     desc: "AI/DS, Biotechnology" },
  { id: "pure_science", name: "Science-adjacent",              desc: "Biotech, Materials, Chemical" },
  { id: "mba",          name: "Management / MBA later",        desc: "Any branch — college strength focus" },
  { id: "undecided",    name: "Not sure yet",                  desc: "Show me all good options" },
];

const GOAL_ICONS = {
  coding:      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  core:        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
  research:    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg>',
  pure_science:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v8L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45L14 10V2z"/><path d="M8.5 2h7"/><path d="M7 16h10"/></svg>',
  mba:         '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>',
  undecided:   '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
};

const ALL_VIEWS = [
  "welcome", "step-0", "step-1", "step-2", "step-3", "step-4",
  "loading", "results", "error",
];

// ── STATE ─────────────────────────────────────────────────────
const state = {
  rank:         null,
  seatCategory: "GM",
  branchPrefs:  [],
  goal:         "undecided",
  ratio:        0.5,
  lastData:     null,
  filterText:   "",
  meta:         null,
};

// ── DOM helpers ───────────────────────────────────────────────
const $ = id => document.getElementById(id);

function esc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const fmt = n => Number(n).toLocaleString("en-IN");

function parseRank(el) {
  if (!el) return null;
  const n = parseInt(el.value.replace(/[^\d]/g, ""), 10);
  return n > 0 ? n : null;
}

function fmtRankInput(el) {
  if (!el) return;
  el.addEventListener("input", () => {
    const n = parseRank(el);
    el.value = n === null ? "" : fmt(n);
  });
}

// ── VIEW SWITCHING ────────────────────────────────────────────
function showView(name) {
  for (const v of ALL_VIEWS) {
    const el = $(`view-${v}`);
    if (el) el.classList.toggle("is-active", v === name);
  }
  const rb = $("restart-btn");
  if (rb) rb.hidden = (name === "welcome");
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
}

// ── CATEGORY (seat_category) ─────────────────────────────────
function syncCategory() {
  const s1 = $("quota-select");
  if (s1) s1.value = state.seatCategory;
  const s2 = $("panel-quota-select");
  if (s2) s2.value = state.seatCategory;
}

function categoryLabel(value) {
  const found = (state.meta?.seat_categories || []).find(c => c.value === value);
  return found ? found.label : value;
}

// ── BRANCH PREFERENCE GRID (STEP 2) ──────────────────────────
function buildBranchGrid() {
  const grid = $("branch-grid");
  if (!grid) return;
  const options = state.meta?.branch_preferences || [];
  grid.innerHTML = options.map(b => `
    <label class="branch-chip${state.branchPrefs.includes(b.value) ? " is-selected" : ""}" data-value="${esc(b.value)}">
      <input type="checkbox" value="${esc(b.value)}" ${state.branchPrefs.includes(b.value) ? "checked" : ""} />
      <span>${esc(b.label)}</span>
    </label>`).join("");

  grid.querySelectorAll(".branch-chip").forEach(chip => {
    chip.addEventListener("click", (e) => {
      e.preventDefault();
      const val = chip.dataset.value;
      const idx = state.branchPrefs.indexOf(val);
      if (idx === -1) state.branchPrefs.push(val);
      else state.branchPrefs.splice(idx, 1);
      chip.classList.toggle("is-selected", state.branchPrefs.includes(val));
      chip.querySelector("input").checked = state.branchPrefs.includes(val);
    });
  });
}

function branchPrefsLabel() {
  if (!state.branchPrefs.length) return "All";
  const opts = state.meta?.branch_preferences || [];
  return state.branchPrefs
    .map(v => opts.find(o => o.value === v)?.label || v)
    .join(", ");
}

// ── GOAL GRID ─────────────────────────────────────────────────
function buildGoalGrid() {
  const grid = $("goal-grid");
  if (!grid) return;
  grid.innerHTML = "";
  for (const g of GOALS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "goal-card" + (state.goal === g.id ? " is-selected" : "");
    btn.dataset.goal = g.id;
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", state.goal === g.id ? "true" : "false");
    btn.innerHTML = `
      <span class="goal-card__icon" aria-hidden="true">${GOAL_ICONS[g.id] || ""}</span>
      <span>
        <span class="goal-card__name">${esc(g.name)}</span>
        <span class="goal-card__desc">${esc(g.desc)}</span>
      </span>`;
    btn.addEventListener("click", () => {
      state.goal = g.id;
      grid.querySelectorAll(".goal-card").forEach(c => {
        const on = c === btn;
        c.classList.toggle("is-selected", on);
        c.setAttribute("aria-checked", on ? "true" : "false");
      });
      syncPanelGoal();
    });
    grid.appendChild(btn);
  }
}

function syncPanelGoal() {
  const sel = $("panel-goal");
  if (sel) sel.value = state.goal;
}

// ── REVIEW (STEP 4) ───────────────────────────────────────────
function populateReview() {
  const rv = $("rv-rank-val");
  const qv = $("rv-quota-val");
  const bv = $("rv-branches-val");
  const gv = $("rv-goal-val");
  if (rv) rv.textContent = state.rank ? fmt(state.rank) : "—";
  if (qv) qv.textContent = categoryLabel(state.seatCategory);
  if (bv) bv.textContent = branchPrefsLabel();
  if (gv) gv.textContent = GOALS.find(g => g.id === state.goal)?.name || state.goal;
}

// ── NAVIGATION ────────────────────────────────────────────────
function goToStep(n) {
  if (n === 4) populateReview();
  showView(`step-${n}`);
}

// ── LOADING ANIMATION ─────────────────────────────────────────
const LOADING_LINES = [
  "Reading KCET 2025 cutoffs…",
  "Matching your rank to colleges…",
  "Sorting Safe, Target and Dream…",
  "Almost there…",
];

let _loadTimer = null;

function startLoading() {
  let i = 0;
  const el = $("loading-text");
  if (el) el.textContent = LOADING_LINES[0];
  _loadTimer = setInterval(() => {
    i = (i + 1) % LOADING_LINES.length;
    if (el) el.textContent = LOADING_LINES[i];
  }, 1100);
}

function stopLoading() {
  clearInterval(_loadTimer);
  _loadTimer = null;
}

// ── API ───────────────────────────────────────────────────────
async function apiRequest(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      msg = body.detail ? JSON.stringify(body.detail) : msg;
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

function buildPayload(extra = {}) {
  return {
    rank: state.rank,
    seat_category: state.seatCategory,
    goal: state.goal,
    branch_preferences: state.branchPrefs.slice(),
    brand_branch_ratio: state.ratio,
    bucket: "all",
    ...extra,
  };
}

// ── SUBMIT ────────────────────────────────────────────────────
async function submitProfile() {
  if (!state.rank) {
    showView("step-0");
    return;
  }
  showView("loading");
  startLoading();
  try {
    const data = await apiRequest("/api/kcet/recommend", {
      method: "POST",
      body: JSON.stringify(buildPayload()),
    });
    stopLoading();
    state.lastData = data;
    syncPanel();
    renderResults(data);
    showView("results");
  } catch (err) {
    stopLoading();
    const el = $("error-message");
    if (el) el.textContent = err.message || "Something went wrong. Please try again.";
    showView("error");
  }
}

// ── LIVE PANEL ────────────────────────────────────────────────
let _panelTimer = null;

function setPanelUpdating(on) {
  const el = $("panel-updating");
  if (el) el.hidden = !on;
  document.querySelector(".results-main")?.classList.toggle("is-refreshing", on);
}

function schedulePanelUpdate() {
  setPanelUpdating(true);
  clearTimeout(_panelTimer);
  _panelTimer = setTimeout(runPanelUpdate, 450);
}

async function runPanelUpdate() {
  const r = parseRank($("panel-rank"));
  if (!r) { setPanelUpdating(false); return; }
  state.rank         = r;
  state.seatCategory = $("panel-quota-select")?.value || state.seatCategory;
  state.goal         = $("panel-goal")?.value || state.goal;
  state.ratio         = parseFloat($("panel-ratio")?.value ?? state.ratio);
  try {
    const data = await apiRequest("/api/kcet/recommend", {
      method: "POST",
      body: JSON.stringify(buildPayload()),
    });
    state.lastData = data;
    renderResults(data, { keepFilter: true });
  } catch (e) {
    console.warn("Panel update failed:", e?.message);
  } finally {
    setPanelUpdating(false);
  }
}

function syncPanel() {
  const pr = $("panel-rank");
  if (pr) pr.value = fmt(state.rank);
  syncCategory();
  syncPanelGoal();
  const pratio = $("panel-ratio");
  if (pratio) pratio.value = state.ratio;
}

// ── FETCH A SINGLE BUCKET UNCAPPED ("show all N") ────────────
const _bucketCache = {};

async function fetchFullBucket(bucketKey) {
  if (_bucketCache[bucketKey]) return _bucketCache[bucketKey];
  const data = await apiRequest("/api/kcet/recommend", {
    method: "POST",
    body: JSON.stringify(buildPayload({ bucket: bucketKey })),
  });
  _bucketCache[bucketKey] = data.recommendations || [];
  return _bucketCache[bucketKey];
}

// ── RESULTS ───────────────────────────────────────────────────
const SEC_ORDER   = ["Target", "Reach", "Safe"];
const SEC_DISPLAY = { Safe: "Safe", Target: "Target", Reach: "Dream" };
const SEC_TONE    = { Safe: "safe", Target: "target", Reach: "reach" };
const SEC_BUCKET_KEY = { Safe: "safe", Target: "target", Reach: "dream" };
const CARD_LIMIT = 25;

function renderResults(data, { keepFilter = false } = {}) {
  if (!keepFilter) { state.filterText = ""; Object.keys(_bucketCache).forEach(k => delete _bucketCache[k]); }

  const chips = $("profile-chips");
  if (chips) {
    chips.innerHTML = [
      `Rank <strong>${fmt(state.rank)}</strong>`,
      esc(categoryLabel(state.seatCategory)),
      esc(GOALS.find(g => g.id === state.goal)?.name || state.goal),
    ].map(c => `<span class="pchip">${c}</span>`).join("");
  }

  // Notes / banners
  const notesEl = $("kcet-notes");
  if (notesEl) {
    const notes = data.notes || [];
    notesEl.innerHTML = notes.map(n => `<div class="kcet-note">${esc(n)}</div>`).join("");
  }

  const recs = (data.recommendations || []).map(r => ({ ...r }));
  const grouped = { Safe: [], Target: [], Reach: [] };
  for (const r of recs) if (grouped[r.category]) grouped[r.category].push(r);

  const counts = data.counts || {};
  const byCat = counts.by_category || {};
  const total = counts.total || 0;

  const q = state.filterText.toLowerCase();
  const passesFilter = r => !q || r.institute.toLowerCase().includes(q) || r.program.toLowerCase().includes(q);

  const container = $("results-sections-container");
  if (!container) return;

  if (total === 0) {
    container.innerHTML = `<div class="rsection__empty">No colleges match your criteria. Try entering a different rank or checking another category.</div>`;
    return;
  }

  container.innerHTML = SEC_ORDER.map(cat => {
    const shown = grouped[cat].filter(passesFilter);
    const eligibleCount = byCat[cat] || 0;
    const tone  = SEC_TONE[cat];
    const label = SEC_DISPLAY[cat];
    const visible = shown.slice(0, CARD_LIMIT);
    const remaining = eligibleCount - visible.length;

    const content = shown.length === 0
      ? `<p class="rsection__empty">${
          eligibleCount === 0 ? "No programmes in this category for your rank."
          : q ? "No results match your search here."
          : "Results loading…"
        }</p>`
      : visible.map((r, i) => makeCard(r, i)).join("");

    const moreBtn = (!q && remaining > 0)
      ? `<div style="text-align:center;margin:20px 0 8px">
           <button type="button" class="btn btn--ghost" data-more="${cat}" style="gap:6px;font-size:.92rem">Show ${fmt(remaining)} more ▾</button>
         </div>`
      : "";

    return `
      <section class="rsection" id="section-${cat.toLowerCase()}">
        <div class="rsection__head">
          <span class="rsection__tag tone-${tone}">${label}</span>
          <span class="rsection__count">Showing ${fmt(visible.length)} of ${fmt(eligibleCount)}</span>
        </div>
        <div class="rsection__collapse" id="collapse-${cat.toLowerCase()}">
          <div class="rsection__collapse-inner" id="cards-${cat.toLowerCase()}">
            ${content}
          </div>
          ${moreBtn}
        </div>
      </section>`;
  }).join("");

  container.querySelectorAll("[data-more]").forEach(btn => {
    btn.addEventListener("click", () => expandSection(btn.dataset.more));
  });
}

async function expandSection(cat) {
  const bucketKey = SEC_BUCKET_KEY[cat];
  const btn = document.querySelector(`[data-more="${cat}"]`);
  if (btn) btn.textContent = "Loading…";
  try {
    const full = await fetchFullBucket(bucketKey);
    const cardsEl = $(`cards-${cat.toLowerCase()}`);
    if (cardsEl) {
      const q = state.filterText.toLowerCase();
      const filtered = full.filter(r => !q || r.institute.toLowerCase().includes(q) || r.program.toLowerCase().includes(q));
      cardsEl.innerHTML = filtered.map((r, i) => makeCard(r, i)).join("");
    }
    const countEl = document.querySelector(`#section-${cat.toLowerCase()} .rsection__count`);
    if (countEl) countEl.textContent = `Showing ${fmt(full.length)} of ${fmt(full.length)}`;
    btn?.parentElement?.remove();
  } catch (e) {
    if (btn) btn.textContent = "Failed to load — try again";
  }
}

// ── CARD ──────────────────────────────────────────────────────
function makeCard(rec, idx) {
  const catL  = rec.category === "Reach" ? "reach" : rec.category.toLowerCase();
  const delay = Math.min(idx * 40, 400);
  const rank  = state.rank;
  const cut   = Math.round(rec.closing_rank);

  const lo  = Math.min(rank, cut) * 0.75;
  const hi  = Math.max(rank, cut) * 1.25 || 1;
  const pos = (v) => {
    const range = hi - lo;
    if (range <= 0) return 50;
    return Math.min(Math.max(((v - lo) / range) * 100, 3), 97);
  };
  const cutPos = pos(cut);
  const youPos = pos(rank);
  const winLeft  = Math.min(cutPos, youPos);
  const winRight = Math.max(cutPos, youPos);

  const star = rec.matched_interest
    ? `<span class="ccard__star" title="Fits your stated goal">
         <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8L12 2z"/></svg>
         fits your goal</span>`
    : "";

  const prob = rec.admission_probability;
  const probColor = prob >= 70 ? "var(--pine, #175c4c)" : prob >= 35 ? "#a87714" : "#bf5b3c";

  return `
    <article class="ccard ccard--${catL}" style="animation-delay:${delay}ms">
      <div class="ccard__meta">
        <span class="tag tag--govt">KEA</span>
        <span class="tag">${esc(rec.seat_category)}</span>
        <span class="ccard__quality">quality ${rec.quality_score?.toFixed(1) ?? "—"}/10</span>
        ${star}
      </div>
      <h3 class="ccard__institute">${esc(rec.institute)}</h3>
      <p class="ccard__branch">${esc(rec.program)}</p>

      <div class="rankbar">
        <div class="rankbar__track">
          <div class="rankbar__window" style="left:${winLeft.toFixed(1)}%;right:${(100 - winRight).toFixed(1)}%"></div>
          <div class="rankbar__you" style="left:${youPos.toFixed(1)}%" title="Your rank: ${fmt(rank)}"></div>
        </div>
        <div class="rankbar__labels">
          <span>Cutoff <strong>${fmt(cut)}</strong></span>
          <span>Your rank <strong>${fmt(rank)}</strong></span>
        </div>
        <p class="rankbar__verdict">${esc(rec.reason)}</p>
      </div>

      <div class="ccard__foot">
        ${prob !== null && prob !== undefined ? `<span class="ccard__prob" style="color:${probColor}">${prob}% chance</span>` : "<span></span>"}
        <span>${esc(rec.seat_category_label)}</span>
        <span>via KCET 2025 R1</span>
      </div>
    </article>`;
}

// ── META ──────────────────────────────────────────────────────
async function loadMeta() {
  try {
    const meta = await apiRequest("/api/kcet/meta");
    state.meta = meta;
    const note = $("data-note");
    if (note) note.textContent = `KCET 2025 · ${fmt(meta.total_programs)} programmes · ${fmt(meta.total_institutes)} colleges`;

    const q1 = $("quota-select");
    const q2 = $("panel-quota-select");
    if (meta.seat_categories && meta.seat_categories.length) {
      const opts = meta.seat_categories.map(c => `<option value="${esc(c.value)}">${esc(c.value)} — ${esc(c.label)}</option>`).join("");
      if (q1) q1.innerHTML = opts;
      if (q2) q2.innerHTML = opts;
      if (!meta.seat_categories.some(c => c.value === state.seatCategory)) {
        state.seatCategory = meta.seat_categories.find(c => c.value === "GM")?.value || meta.seat_categories[0].value;
      }
      syncCategory();
    }

    buildBranchGrid();

    const gLabels = {};
    for (const g of meta.goals || []) gLabels[g.value] = g.label;
    for (const g of GOALS) if (gLabels[g.id]) g.name = gLabels[g.id];
    buildGoalGrid();

    const sel = $("panel-goal");
    if (sel) {
      sel.innerHTML = GOALS.map(g => `<option value="${g.id}">${esc(g.name)}</option>`).join("");
      sel.value = state.goal;
    }
  } catch (e) {
    console.error("Meta load failed:", e?.message);
    buildGoalGrid();
  }
}

// ── EVENTS ────────────────────────────────────────────────────
function bindEvents() {
  $("begin-btn")?.addEventListener("click", () => goToStep(0));

  $("restart-btn")?.addEventListener("click", () => {
    state.rank = null; state.seatCategory = "GM"; state.goal = "undecided";
    state.branchPrefs = []; state.ratio = 0.5;
    syncCategory();
    showView("welcome");
  });

  // Step 0: rank
  fmtRankInput($("kcet-rank"));
  $("kcet-rank")?.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); validateAndNext0(); }
  });
  $("next-0")?.addEventListener("click", validateAndNext0);
  $("back-0")?.addEventListener("click", () => showView("welcome"));

  // Step 1: category
  $("quota-select")?.addEventListener("change", e => {
    state.seatCategory = e.target.value;
    syncCategory();
  });
  $("next-1")?.addEventListener("click", () => goToStep(2));
  $("back-1")?.addEventListener("click", () => goToStep(0));

  // Step 2: branch preferences
  $("next-2")?.addEventListener("click", () => goToStep(3));
  $("skip-2")?.addEventListener("click", () => { state.branchPrefs = []; buildBranchGrid(); goToStep(3); });
  $("back-2")?.addEventListener("click", () => goToStep(1));

  // Step 3: goal + ratio
  $("back-3")?.addEventListener("click", () => goToStep(2));
  $("ratio-slider")?.addEventListener("input", e => { state.ratio = parseFloat(e.target.value); });
  $("next-3")?.addEventListener("click", () => goToStep(4));

  // Step 4: review / confirm
  $("back-4")?.addEventListener("click", () => goToStep(3));
  $("see-colleges-btn")?.addEventListener("click", submitProfile);

  $("rv-rank")    ?.addEventListener("click", () => goToStep(0));
  $("rv-quota")   ?.addEventListener("click", () => goToStep(1));
  $("rv-branches")?.addEventListener("click", () => goToStep(2));
  $("rv-goal")    ?.addEventListener("click", () => goToStep(3));

  // Error page
  $("retry-btn")     ?.addEventListener("click", submitProfile);
  $("error-edit-btn")?.addEventListener("click", () => goToStep(0));

  // Panel
  fmtRankInput($("panel-rank"));
  $("panel-rank")?.addEventListener("input", schedulePanelUpdate);
  $("panel-quota-select")?.addEventListener("change", e => {
    state.seatCategory = e.target.value;
    schedulePanelUpdate();
  });
  $("panel-goal")?.addEventListener("change", () => {
    state.goal = $("panel-goal").value;
    schedulePanelUpdate();
  });
  $("panel-ratio")?.addEventListener("input", () => {
    state.ratio = parseFloat($("panel-ratio").value);
    schedulePanelUpdate();
  });

  const pt = $("panel-toggle");
  const pb = $("panel-body");
  pt?.addEventListener("click", () => {
    const open = pt.getAttribute("aria-expanded") === "true";
    pt.setAttribute("aria-expanded", open ? "false" : "true");
    pb?.classList.toggle("is-open", !open);
  });

  $("results-search-input")?.addEventListener("input", e => {
    state.filterText = e.target.value;
    if (state.lastData) renderResults(state.lastData, { keepFilter: true });
  });

  $("share-btn")?.addEventListener("click", () => {
    const msg = `My KCET rank ${fmt(state.rank)} (${state.seatCategory}). Check out Disha for free college predictions → ${location.href}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(msg)}`, "_blank", "noopener");
  });
}

function validateAndNext0() {
  const rank = parseRank($("kcet-rank"));
  const err  = $("error-rank");
  if (!rank) {
    if (err) { err.textContent = "Please enter a valid KCET rank."; err.hidden = false; }
    $("kcet-rank")?.focus();
    return;
  }
  if (err) err.hidden = true;
  state.rank = rank;
  goToStep(1);
}

// ── INIT ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  buildGoalGrid();
  bindEvents();
  loadMeta();
  showView("welcome");
});
