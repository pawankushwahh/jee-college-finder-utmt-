"use strict";

/* ═══════════════════════════════════════════════════════════════
   Disha — KCET (standalone SPA, NO shared JEE/COMEDK code)

   View IDs (each step is its own <section>):
     view-welcome  view-step-0  view-step-1  view-step-2  view-step-3
     view-loading  view-results  view-error

   Flow: rank -> category -> branch preferences -> review
   Career goal and the branch/college priority toggle are NOT part of the
   guided flow — matching the real JEE page, which explicitly removed its
   interest step from onboarding. Both live only in the results toolbar,
   where changing them triggers a live re-fetch, same as editing the panel.

   API:  GET  /api/kcet/meta
         POST /api/kcet/recommend
   ═══════════════════════════════════════════════════════════════ */

const ALL_VIEWS = [
  "welcome", "step-0", "step-1", "step-2", "step-3",
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

function goalName(id) {
  const found = (state.meta?.goals || []).find(g => g.value === id);
  return found ? found.label : id;
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

// ── BRANCH PREFERENCE GRIDS (flow step 2 + results panel) ────
function branchChipsHtml() {
  const options = state.meta?.branch_preferences || [];
  return options.map(b => `
    <label class="branch-chip${state.branchPrefs.includes(b.value) ? " is-selected" : ""}" data-value="${esc(b.value)}">
      <input type="checkbox" value="${esc(b.value)}" ${state.branchPrefs.includes(b.value) ? "checked" : ""} />
      <span>${esc(b.label)}</span>
    </label>`).join("");
}

function bindBranchChipClicks(grid, onToggle) {
  grid.querySelectorAll(".branch-chip").forEach(chip => {
    chip.addEventListener("click", (e) => {
      e.preventDefault();
      const val = chip.dataset.value;
      const idx = state.branchPrefs.indexOf(val);
      if (idx === -1) state.branchPrefs.push(val);
      else state.branchPrefs.splice(idx, 1);
      document.querySelectorAll(`.branch-chip[data-value="${val}"]`).forEach(c => {
        c.classList.toggle("is-selected", state.branchPrefs.includes(val));
        const inp = c.querySelector("input");
        if (inp) inp.checked = state.branchPrefs.includes(val);
      });
      onToggle?.();
    });
  });
}

function buildBranchGrid() {
  const grid = $("branch-grid");
  if (!grid) return;
  grid.innerHTML = branchChipsHtml();
  bindBranchChipClicks(grid);
}

function buildPanelBranchGrid() {
  const grid = $("panel-branch-grid");
  if (!grid) return;
  grid.innerHTML = branchChipsHtml();
  bindBranchChipClicks(grid, () => {
    buildBranchGrid();
    schedulePanelUpdate();
  });
}

function branchPrefsLabel() {
  if (!state.branchPrefs.length) return "All";
  const opts = state.meta?.branch_preferences || [];
  return state.branchPrefs
    .map(v => opts.find(o => o.value === v)?.label || v)
    .join(", ");
}

// ── REVIEW (STEP 3) ───────────────────────────────────────────
function populateReview() {
  const rv = $("rv-rank-val");
  const qv = $("rv-quota-val");
  const bv = $("rv-branches-val");
  if (rv) rv.textContent = state.rank ? fmt(state.rank) : "—";
  if (qv) qv.textContent = categoryLabel(state.seatCategory);
  if (bv) bv.textContent = branchPrefsLabel();
}

// ── NAVIGATION ────────────────────────────────────────────────
function goToStep(n) {
  if (n === 3) populateReview();
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

// ── LIVE PANEL / TOOLBAR UPDATES ───────────────────────────────
let _panelTimer = null;

function setPanelUpdating(on) {
  const el = $("panel-updating");
  if (el) el.hidden = !on;
  document.querySelector(".results-main")?.classList.toggle("is-refreshing", on);
}

function schedulePanelUpdate() {
  setPanelUpdating(true);
  clearTimeout(_panelTimer);
  _panelTimer = setTimeout(runPanelUpdate, 420);
}

async function runPanelUpdate() {
  const r = parseRank($("panel-rank"));
  if (!r) { setPanelUpdating(false); return; }
  state.rank         = r;
  state.seatCategory = $("panel-quota-select")?.value || state.seatCategory;
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
  buildPanelBranchGrid();
  updatePriorityUI();
}

// ── TOOLBAR: goal select + branch/college priority toggle ─────
function buildToolbarGoalSelect() {
  const sel = $("toolbar-goal");
  if (!sel) return;
  const opts = state.meta?.goals || [];
  sel.innerHTML = opts.map(g => `<option value="${esc(g.value)}">${esc(g.label)}</option>`).join("");
  sel.value = state.goal;
}

function updatePriorityUI() {
  const buttons = { "0.2": $("priority-branch"), "0.5": $("priority-balanced"), "0.8": $("priority-college") };
  Object.entries(buttons).forEach(([val, btn]) => {
    if (btn) btn.classList.toggle("is-active", Math.abs(state.ratio - parseFloat(val)) < 0.15);
  });

  const branchFull = document.querySelector("#priority-branch .full-label");
  const branchShort = document.querySelector("#priority-branch .short-label");
  if (branchFull && branchShort) {
    if (state.goal && state.goal !== "undecided") {
      const name = goalName(state.goal);
      branchFull.textContent = `Favour Branch (${name})`;
      branchShort.textContent = `Branch (${name})`;
    } else {
      branchFull.textContent = "Favour Branch";
      branchShort.textContent = "Branch";
    }
  }

  const tooltip = $("priority-goal-tooltip");
  if (tooltip) {
    const favourBranchActive = Math.abs(state.ratio - 0.2) < 0.15;
    const goalUndecided = !state.goal || state.goal === "undecided";
    tooltip.hidden = !(favourBranchActive && goalUndecided);
  }

  updateSpectrumNote();
}

function updateSpectrumNote() {
  const el = $("spectrum-note");
  if (!el) return;
  const th = state.lastData?.thresholds || {};
  const safeMargin = th.safe_margin ?? 0.15;
  const upperMargin = th.upper_margin ?? 0.25;
  el.innerHTML =
    `<strong>Safe:</strong> your rank clears last year's cutoff by more than ${Math.round(safeMargin * 100)}% of it (clamped to a sensible rank range). &nbsp;` +
    `<strong>Target:</strong> your rank sits at or just above the cutoff. &nbsp;` +
    `<strong>Dream:</strong> within ${Math.round(upperMargin * 100)}% past the cutoff — ambitious but possible.`;
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

// ── RANK RULER — every eligible pick on one log rank axis ─────
// KCET closing ranks run up to ~250,000 in the 2025 GM data (vs. COMEDK's
// ~112,000 and JEE's per-exam ranges), so the axis and tick set are KCET's
// own, not reused from either.
const RANK_AXIS_MAX = 300000;
const LOG_AXIS_MAX = Math.log10(RANK_AXIS_MAX);

function rankPosScoped(rank, logMin, logMax) {
  const r = Math.min(Math.max(Number(rank) || 1, 1), RANK_AXIS_MAX);
  const logR = Math.log10(r);
  const span = logMax - logMin;
  if (span <= 0) return 50;
  return Math.min(Math.max(((logR - logMin) / span) * 100, 0.5), 99.5);
}

const ALL_TICKS = [
  { rank: 1, label: "1" }, { rank: 10, label: "10" }, { rank: 100, label: "100" },
  { rank: 500, label: "500" }, { rank: 1000, label: "1K" }, { rank: 2000, label: "2K" },
  { rank: 5000, label: "5K" }, { rank: 10000, label: "10K" }, { rank: 20000, label: "20K" },
  { rank: 50000, label: "50K" }, { rank: 100000, label: "1L" }, { rank: 200000, label: "2L" },
  { rank: 300000, label: "3L" },
];

function ticksForRange(logMin, logMax) {
  const visible = ALL_TICKS.filter(t => {
    const logR = Math.log10(t.rank || 1);
    return logR >= logMin - 0.05 && logR <= logMax + 0.05;
  });
  return visible.length > 8 ? visible.filter((_, i) => i % 2 === 0) : visible;
}

const rulerZoomState = {};
const MIN_LOG_SPAN = 0.4;
const RULER_ID = "kcet";

function computeAutoRange(items, youRank) {
  const ranks = items.map(r => r.closing_rank);
  if (youRank) ranks.push(youRank);
  if (!ranks.length) return { logMin: 1, logMax: LOG_AXIS_MAX };
  const minR = Math.max(1, Math.min(...ranks));
  const maxR = Math.min(RANK_AXIS_MAX, Math.max(...ranks));
  const logMin = Math.log10(minR);
  const logMax = Math.log10(maxR);
  const padding = Math.max((logMax - logMin) * 0.15, 0.3);
  return { logMin: Math.max(0, logMin - padding), logMax: Math.min(LOG_AXIS_MAX, logMax + padding) };
}

function rulerGroupHtml(recs) {
  if (!recs.length) return "";
  const youRank = state.rank;
  const sorted = recs.slice().sort((a, b) => a.closing_rank - b.closing_rank);

  const autoRange = computeAutoRange(recs, youRank);
  if (!rulerZoomState[RULER_ID]) {
    rulerZoomState[RULER_ID] = {
      logMin: autoRange.logMin, logMax: autoRange.logMax,
      defaultLogMin: autoRange.logMin, defaultLogMax: autoRange.logMax,
    };
  } else {
    rulerZoomState[RULER_ID].defaultLogMin = autoRange.logMin;
    rulerZoomState[RULER_ID].defaultLogMax = autoRange.logMax;
  }
  rulerZoomState[RULER_ID].dotLogs = sorted.map(r => Math.log10(r.closing_rank));
  const { logMin, logMax } = rulerZoomState[RULER_ID];

  const numLanes = 8;
  const lanes = new Array(numLanes).fill(-100);
  const dots = sorted.map((r) => {
    const cat = r.category === "Reach" ? "reach" : r.category.toLowerCase();
    const absPos = Math.log10(r.closing_rank);
    let bestLane = 0, maxDist = -1;
    for (let l = 0; l < numLanes; l++) {
      const dist = absPos - lanes[l];
      if (dist > maxDist) { maxDist = dist; bestLane = l; }
    }
    lanes[bestLane] = absPos;
    const topPct = 10 + (bestLane / (numLanes - 1)) * 80;
    const leftPct = rankPosScoped(r.closing_rank, logMin, logMax);
    return `<span class="ruler__dot ruler__dot--${cat}" style="left:${leftPct.toFixed(2)}%; top:${topPct.toFixed(2)}%" data-inst="${esc(r.institute)}" data-branch="${esc(r.program)}" data-rank="${r.closing_rank}" data-cat="${cat}" title="${esc(r.institute)} — ${esc(r.program)} (cutoff ${fmt(r.closing_rank)})"></span>`;
  }).join("");

  const visibleTicks = ticksForRange(logMin, logMax);
  const grid = visibleTicks.map(tk => `<span class="ruler__grid" style="left:${rankPosScoped(tk.rank, logMin, logMax).toFixed(2)}%"></span>`).join("");
  const scale = visibleTicks.map(tk => `<span class="ruler__tick" style="left:${rankPosScoped(tk.rank, logMin, logMax).toFixed(2)}%">${tk.label}</span>`).join("");

  const you = youRank
    ? `<div class="ruler__you" style="left:${rankPosScoped(youRank, logMin, logMax).toFixed(2)}%" title="Your rank: ${fmt(youRank)}"><span class="ruler__you-flag">YOU</span></div>`
    : "";
  const headRight = youRank
    ? `<span class="ruler__you-rank">YOU · ${fmt(youRank)}</span>`
    : `<span class="ruler__count">${recs.length} options</span>`;

  return `
    <div class="ruler__group" role="img" aria-label="KCET rank ruler: ${recs.length} options" data-ruler-id="${RULER_ID}">
      <div class="ruler__head">
        <span class="ruler__title">KCET Colleges <span class="ruler__via">via KCET 2025 R1</span></span>
        ${headRight}
      </div>
      <div class="ruler__track-wrap">
        <div class="ruler__track" data-ruler-id="${RULER_ID}" tabindex="0" aria-label="Interactive chart track. Use arrow keys to pan, plus/minus to zoom.">
          ${grid}
          ${dots}
          ${you}
        </div>
        <div class="ruler__zoom-controls">
          <button type="button" class="ruler__zoom-btn" data-action="in" data-ruler-id="${RULER_ID}" title="Zoom in">+</button>
          <button type="button" class="ruler__zoom-btn" data-action="out" data-ruler-id="${RULER_ID}" title="Zoom out">−</button>
          <button type="button" class="ruler__zoom-btn" data-action="reset" data-ruler-id="${RULER_ID}" title="Reset zoom">⟲</button>
        </div>
      </div>
      <div class="ruler__scale">${scale}</div>
    </div>`;
}

function renderRuler(data) {
  const container = $("ruler");
  if (!container) return;
  const recs = data.recommendations || [];
  container.innerHTML = rulerGroupHtml(recs);
  bindRulerInteractions();
}

function rerenderRuler() {
  const data = state.lastData;
  if (!data) return;
  const groupEl = document.querySelector(`.ruler__group[data-ruler-id="${RULER_ID}"]`);
  if (!groupEl) return;
  const html = rulerGroupHtml(data.recommendations || []);
  if (!html) return;
  const temp = document.createElement("div");
  temp.innerHTML = html;
  const newTrack = temp.querySelector(".ruler__track");
  const newScale = temp.querySelector(".ruler__scale");
  const oldTrack = groupEl.querySelector(".ruler__track");
  const oldScale = groupEl.querySelector(".ruler__scale");
  if (oldTrack && newTrack) oldTrack.innerHTML = newTrack.innerHTML;
  if (oldScale && newScale) oldScale.innerHTML = newScale.innerHTML;
}

function applyClampedRange(zs, newMin, newMax) {
  const maxSpan = (zs.defaultLogMax || LOG_AXIS_MAX) - (zs.defaultLogMin || 0);
  let span = newMax - newMin;
  if (span > maxSpan) { const c = (newMin + newMax) / 2; newMin = c - maxSpan / 2; newMax = c + maxSpan / 2; }
  if (newMin < 0) { newMax += -newMin; newMin = 0; }
  if (newMax > LOG_AXIS_MAX) { newMin -= (newMax - LOG_AXIS_MAX); newMax = LOG_AXIS_MAX; }
  newMin = Math.max(0, newMin);
  newMax = Math.min(LOG_AXIS_MAX, newMax);
  if (newMax - newMin < 0.001) newMax = newMin + 0.001;
  zs.logMin = newMin; zs.logMax = newMax;
}

function applyZoom(action) {
  const zs = rulerZoomState[RULER_ID];
  if (!zs) return;
  const span = zs.logMax - zs.logMin;
  if (action === "in") {
    const shrink = span * 0.15;
    if (span - shrink * 2 < MIN_LOG_SPAN) return;
    applyClampedRange(zs, zs.logMin + shrink, zs.logMax - shrink);
  } else if (action === "out") {
    const grow = span * 0.2;
    applyClampedRange(zs, zs.logMin - grow, zs.logMax + grow);
  } else if (action === "reset") {
    zs.logMin = zs.defaultLogMin; zs.logMax = zs.defaultLogMax;
  }
  rerenderRuler();
}

function applyPan(deltaLog) {
  const zs = rulerZoomState[RULER_ID];
  if (!zs) return;
  applyClampedRange(zs, zs.logMin + deltaLog, zs.logMax + deltaLog);
  rerenderRuler();
}

function bindRulerInteractions() {
  document.querySelectorAll(".ruler__zoom-btn").forEach(btn => {
    if (btn._bound) return;
    btn._bound = true;
    btn.addEventListener("click", (e) => { e.stopPropagation(); applyZoom(btn.dataset.action); });
  });
  document.querySelectorAll(".ruler__track").forEach(track => {
    if (track._bound) return;
    track._bound = true;
    track.addEventListener("wheel", (e) => { e.preventDefault(); applyZoom(e.deltaY < 0 ? "in" : "out"); }, { passive: false });
    track.addEventListener("keydown", (e) => {
      const zs = rulerZoomState[RULER_ID];
      if (!zs) return;
      const span = zs.logMax - zs.logMin;
      if (e.key === "ArrowLeft") { e.preventDefault(); applyPan(-span * 0.1); }
      if (e.key === "ArrowRight") { e.preventDefault(); applyPan(span * 0.1); }
      if (e.key === "+" || e.key === "=") { e.preventDefault(); applyZoom("in"); }
      if (e.key === "-") { e.preventDefault(); applyZoom("out"); }
      if (e.key === "0") { e.preventDefault(); applyZoom("reset"); }
    });
    let dragging = false, startX = 0, startMin = 0, startMax = 0;
    track.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".ruler__dot") || e.target.closest(".ruler__you")) return;
      const zs = rulerZoomState[RULER_ID];
      if (!zs) return;
      dragging = true; startX = e.clientX; startMin = zs.logMin; startMax = zs.logMax;
      track.setPointerCapture(e.pointerId);
      track.style.cursor = "grabbing";
    });
    track.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const zs = rulerZoomState[RULER_ID];
      if (!zs) return;
      const dx = e.clientX - startX;
      const span = startMax - startMin;
      const deltaLog = -(dx / (track.offsetWidth || 1)) * span;
      applyClampedRange(zs, startMin + deltaLog, startMax + deltaLog);
      rerenderRuler();
    });
    const stop = () => { dragging = false; track.style.cursor = ""; };
    track.addEventListener("pointerup", stop);
    track.addEventListener("pointercancel", stop);
  });
}

// ── RESULTS ───────────────────────────────────────────────────
const SEC_ORDER   = ["Target", "Reach", "Safe"];
const SEC_DISPLAY = { Safe: "Safe", Target: "Target", Reach: "Dream" };
const SEC_TONE    = { Safe: "safe", Target: "target", Reach: "reach" };
const SEC_BUCKET_KEY = { Safe: "safe", Target: "target", Reach: "dream" };
const CARD_LIMIT = 25;

function countUp(el, target) {
  if (!el) return;
  el.textContent = fmt(target);
}

function renderResults(data, { keepFilter = false } = {}) {
  if (!keepFilter) { state.filterText = ""; Object.keys(_bucketCache).forEach(k => delete _bucketCache[k]); }

  const chips = $("profile-chips");
  if (chips) {
    chips.innerHTML = [
      `Rank <strong>${fmt(state.rank)}</strong>`,
      esc(categoryLabel(state.seatCategory)),
      esc(goalName(state.goal)),
    ].map(c => `<span class="pchip">${c}</span>`).join("");
  }

  const notesEl = $("kcet-notes");
  if (notesEl) {
    const notes = data.notes || [];
    notesEl.innerHTML = notes.map(n => `<div class="kcet-note">${esc(n)}</div>`).join("");
  }

  const counts = data.counts || {};
  const byCat = counts.by_category || {};
  const total = counts.total || 0;

  countUp($("zone-count-safe"), byCat.Safe || 0);
  countUp($("zone-count-target"), byCat.Target || 0);
  countUp($("zone-count-reach"), byCat.Reach || 0);
  document.querySelectorAll(".zone").forEach(z => {
    z.classList.toggle("is-empty", !(byCat[z.dataset.zone] > 0));
  });
  updateSpectrumNote();

  renderRuler(data);

  const recs = (data.recommendations || []).map(r => ({ ...r }));
  const grouped = { Safe: [], Target: [], Reach: [] };
  for (const r of recs) if (grouped[r.category]) grouped[r.category].push(r);

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
    buildToolbarGoalSelect();
  } catch (e) {
    console.error("Meta load failed:", e?.message);
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

  // Step 3: review / confirm
  $("back-3")?.addEventListener("click", () => goToStep(2));
  $("see-colleges-btn")?.addEventListener("click", submitProfile);

  $("rv-rank")    ?.addEventListener("click", () => goToStep(0));
  $("rv-quota")   ?.addEventListener("click", () => goToStep(1));
  $("rv-branches")?.addEventListener("click", () => goToStep(2));

  // Error page
  $("retry-btn")     ?.addEventListener("click", submitProfile);
  $("error-edit-btn")?.addEventListener("click", () => goToStep(0));

  // Sidebar panel (rank + category + branches — core identity inputs)
  fmtRankInput($("panel-rank"));
  $("panel-rank")?.addEventListener("input", schedulePanelUpdate);
  $("panel-quota-select")?.addEventListener("change", e => {
    state.seatCategory = e.target.value;
    schedulePanelUpdate();
  });

  const pt = $("panel-toggle");
  const pb = $("panel-body");
  pt?.addEventListener("click", () => {
    const open = pt.getAttribute("aria-expanded") === "true";
    pt.setAttribute("aria-expanded", open ? "false" : "true");
    pb?.classList.toggle("is-open", !open);
  });

  // Toolbar: goal select + branch/college priority (secondary refinement,
  // available only once results exist — same as real JEE).
  $("toolbar-goal")?.addEventListener("change", () => {
    state.goal = $("toolbar-goal").value;
    updatePriorityUI();
    schedulePanelUpdate();
  });
  $("priority-toggle")?.addEventListener("click", (e) => {
    const btn = e.target.closest(".view-toggle-btn");
    if (!btn) return;
    state.ratio = parseFloat(btn.dataset.ratio);
    updatePriorityUI();
    schedulePanelUpdate();
  });
  $("priority-goal-focus")?.addEventListener("click", () => {
    const sel = $("toolbar-goal");
    if (sel) { sel.focus(); }
  });

  // Standing spectrum: click a zone to jump to that section
  $("spectrum")?.addEventListener("click", (e) => {
    const zone = e.target.closest(".zone");
    if (!zone) return;
    const target = $(`section-${zone.dataset.zone.toLowerCase()}`);
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  $("toolbar-toggle")?.addEventListener("click", () => {
    const tb = $("toolbar-toggle");
    const body = $("toolbar-body");
    const open = tb.getAttribute("aria-expanded") === "true";
    tb.setAttribute("aria-expanded", open ? "false" : "true");
    body?.classList.toggle("is-open", !open);
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
  bindEvents();
  loadMeta();
  showView("welcome");
});
