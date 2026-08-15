"use strict";

/* ════════════════════════════════════════════════════════════════════════
   Disha — KCET app logic
   Ported from JEE app.js — structurally identical, domain-adapted.

   Views: welcome → guided 4-step flow → loading → results (or error).
   Talks to the KCET backend via apiRequest() defined in api.js.
   ════════════════════════════════════════════════════════════════════════ */

// ── DOM helpers ─────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const fmt = (n) => Number(n).toLocaleString("en-IN");

const prefersReducedMotion =
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let initialStateLoaded = false;

// ── App state ───────────────────────────────────────────────────────────

const state = {
  meta: null,
  step: 0,
  seat_category: "GM",
  branchPrefs: [],          // selected branch-preference values; [] means "Any"
  lastPayload: null,
  lastData: null,
  totalByType: {},
  filterText: "",
  filterTypes: [],
  choices: JSON.parse(localStorage.getItem("disha_kcet_choices") || "[]"),
  view: localStorage.getItem("disha_kcet_view") || "branch",
  expandedColleges: {},
  collapsedSections: { Safe: false, Target: false, Reach: false },
  sortBy: "rank",
  showAllCards: {},
};

const TOTAL_STEPS = 4;

const branchOptions = () => state.meta?.branch_preferences || [];
const branchLabel = (value) => {
  const b = branchOptions().find((o) => o.value === value);
  return b ? b.label : value;
};

// ── Section ordering (same as JEE) ──────────────────────────────────────

const SECTION_ORDER = ["Target", "Reach", "Safe"];
const sectionMeta = (cat) => ({
  Target: { title: "Target", sub: "your best-fit zone" },
  Reach:  { title: "Dream", sub: "ambitious choices" },
  Safe:   { title: "Safe", sub: "strong backups" },
}[cat]);

// ── View switching ──────────────────────────────────────────────────────

const VIEWS = ["welcome", "flow", "loading", "results", "error"];

function showView(name) {
  for (const v of VIEWS) {
    const el = $(`view-${v}`);
    if (el) el.classList.toggle("is-active", v === name);
  }
  const rb = $("restart-btn");
  if (rb) rb.hidden = name === "welcome";
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });

  if (name === "results") {
    const tb = $("toolbar");
    const tbToggle = $("toolbar-toggle");
    if (window.innerWidth <= 900 && tb && tbToggle) {
      tb.classList.add("is-open");
      tbToggle.setAttribute("aria-expanded", "true");
      tb.dataset.autoOpened = "true";
    }
  }

  saveStateToURL();
}

// ── Rank inputs (live Indian-grouping format) ───────────────────────────

function parseRankInput(el) {
  if (!el) return null;
  const digits = el.value.replace(/[^\d]/g, "");
  if (!digits) return null;
  const n = parseInt(digits, 10);
  return n > 0 ? n : null;
}

function attachRankFormatting(el) {
  if (!el) return;
  el.addEventListener("input", () => {
    const n = parseRankInput(el);
    el.value = n === null ? "" : fmt(n);
    saveStateToURL();
  });
}

// ── Guided flow ─────────────────────────────────────────────────────────

const stepButtonLabel = (index) =>
  index === TOTAL_STEPS - 1 ? "See colleges →" : "Continue";

function goToStep(index, { backwards = false } = {}) {
  state.step = index;
  document.querySelectorAll(".step").forEach((s) => {
    const active = Number(s.dataset.step) === index;
    s.hidden = !active;
    if (active) {
      s.classList.toggle("is-back", backwards);
      s.style.animation = "none";
      void s.offsetWidth;
      s.style.animation = "";
    }
  });

  $("flow-progress-fill").style.width = `${((index + 1) / TOTAL_STEPS) * 100}%`;
  $("flow-progressbar").setAttribute("aria-valuenow", String(index + 1));
  $("flow-count").textContent = `${index + 1} / ${TOTAL_STEPS}`;
  $("flow-back").disabled = index === 0;
  $("flow-next").textContent = stepButtonLabel(index);

  if (index === TOTAL_STEPS - 1) renderReview();

  const firstInput = document.querySelector(
    `.step[data-step="${index}"] input, .step[data-step="${index}"] select`
  );
  if (firstInput && window.matchMedia("(min-width: 720px)").matches) firstInput.focus();
  saveStateToURL();
}

function validateStep(index) {
  if (index === 0) {
    const rank = parseRankInput($("kcet-rank"));
    const err = $("error-ranks");
    if (rank === null) {
      if (err) { err.textContent = "Please enter a valid KCET rank."; err.hidden = false; }
      return false;
    }
    if (err) err.hidden = true;
    return true;
  }
  return true;
}

function advanceStep() {
  if (!validateStep(state.step)) return;
  if (state.step < TOTAL_STEPS - 1) {
    goToStep(state.step + 1);
  } else {
    submitProfile();
  }
}

// ── Quota pills ─────────────────────────────────────────────────────────

function setQuota(value) {
  state.seat_category = value;
  syncQuotaRows();
  saveStateToURL();
}

function syncQuotaRows() {
  document
    .querySelectorAll("#seat_category-row .choice, #panel-seat_category-row .choice")
    .forEach((c) => {
      const on = c.dataset.value === state.seat_category;
      c.classList.toggle("is-selected", on);
      c.setAttribute("aria-checked", on ? "true" : "false");
    });
}

function bindQuotaRow(rowId, onChange) {
  const row = $(rowId);
  if (!row) return;
  row.addEventListener("click", (e) => {
    const btn = e.target.closest(".choice");
    if (!btn) return;
    setQuota(btn.dataset.value);
    if (onChange) onChange();
  });
}

// ── Branch-preference chips ─────────────────────────────────────────────

const BRANCH_CHECK_SVG =
  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';

function makeBranchChip(value, label, active) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className =
    "branch-chip" +
    (active ? " is-selected" : "") +
    (value === "" ? " branch-chip--any" : "");
  btn.setAttribute("role", "checkbox");
  btn.setAttribute("aria-checked", active ? "true" : "false");
  btn.dataset.branch = value;
  btn.innerHTML =
    `<span class="branch-chip__check" aria-hidden="true">${BRANCH_CHECK_SVG}</span>` +
    `<span class="branch-chip__label">${escapeHtml(label)}</span>`;
  btn.addEventListener("click", () => toggleBranchPref(value));
  return btn;
}

function buildBranchGrid(grid) {
  if (!grid) return;
  grid.innerHTML = "";
  const anyActive = state.branchPrefs.length === 0;
  grid.appendChild(makeBranchChip("", "Any branch", anyActive));
  for (const b of branchOptions()) {
    grid.appendChild(
      makeBranchChip(b.value, b.label, state.branchPrefs.includes(b.value))
    );
  }
}

function renderBranchGrids() {
  buildBranchGrid($("branch-grid"));
  buildBranchGrid($("panel-branch-grid"));
}

function toggleBranchPref(value) {
  if (value === "") {
    state.branchPrefs = [];
  } else {
    const i = state.branchPrefs.indexOf(value);
    if (i >= 0) state.branchPrefs.splice(i, 1);
    else state.branchPrefs.push(value);
  }
  renderBranchGrids();
  if ($("view-results").classList.contains("is-active")) schedulePanelUpdate();
  saveStateToURL();
}

// ── Review ──────────────────────────────────────────────────────────────

function branchReviewValue() {
  if (!state.branchPrefs.length) return "Any branch";
  return state.branchPrefs.map(branchLabel).join(", ");
}

function renderReview() {
  const rank = parseRankInput($("kcet-rank"));
  const quotaText = state.seat_category === "GM" ? "GM — General Merit" : "KKR — Kalyana Karnataka";

  const rows = [
    { key: "KCET Rank", val: rank ? fmt(rank) : '<small>not given</small>', step: 0 },
    { key: "Quota", val: escapeHtml(quotaText), step: 1 },
    { key: "Branch preference", val: escapeHtml(branchReviewValue()), step: 2 },
  ];

  const list = $("review-list");
  list.innerHTML = "";
  for (const row of rows) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "review__row";
    btn.innerHTML = `<span class="review__key">${escapeHtml(row.key)}</span><span class="review__val">${row.val}</span>`;
    btn.addEventListener("click", () => goToStep(row.step, { backwards: true }));
    li.appendChild(btn);
    list.appendChild(li);
  }
}

// ── Meta loading ────────────────────────────────────────────────────────

async function loadMeta() {
  const offlineEl = $("meta-offline");
  if (offlineEl) offlineEl.hidden = true;
  const beginBtn = $("begin-btn");
  if (beginBtn) beginBtn.disabled = true;
  try {
    const meta = await apiRequest("/api/kcet/meta");
    state.meta = meta;

    if (meta.total_programs) $("program-count").textContent = fmt(meta.total_programs);

    if (meta.seat_categories && meta.seat_categories.length) {
      const opts = meta.seat_categories.map(c => `<button type="button" class="choice" role="radio" aria-checked="false" data-value="${escapeHtml(c.value)}">${escapeHtml(c.label)}</button>`).join("");
      const q1 = $("seat_category-row");
      const q2 = $("panel-seat_category-row");
      if (q1) q1.innerHTML = opts;
      if (q2) q2.innerHTML = opts;
      if (!meta.seat_categories.some(c => c.value === state.seat_category)) {
        state.seat_category = meta.seat_categories[0].value;
      }
      syncQuotaRows();
    }


    renderBranchGrids();
    if (beginBtn) beginBtn.disabled = false;
  } catch {
    if (offlineEl) offlineEl.hidden = false;
  }
}

// ── Submission ──────────────────────────────────────────────────────────

let loadingTimer = null;
let requestSeq = 0;

const LOADING_LINES = [
  "Reading KCET 2025 cutoffs…",
  "Matching your rank to colleges…",
  "Sorting Safe, Target and Dream…",
  "Almost there…",
];

function startLoadingLines() {
  let i = 0;
  $("loading-text").textContent = LOADING_LINES[0];
  loadingTimer = setInterval(() => {
    i = (i + 1) % LOADING_LINES.length;
    $("loading-text").textContent = LOADING_LINES[i];
  }, 1100);
}

function stopLoadingLines() {
  clearInterval(loadingTimer);
  loadingTimer = null;
}

function buildPayload() {
  const rank = parseRankInput($("kcet-rank"));
  const payload = {
    rank: rank || 1,
    seat_category: state.seat_category,
    branch_preferences: state.branchPrefs.slice(),
    bucket: "all",
    max_results: 5000,
    lang: "en",
  };
  return payload;
}

async function submitProfile() {
  state.lastPayload = buildPayload();
  await runRequest(state.lastPayload);
}

// ── Live panel updates ────────────────────────────────────────────────────

let panelDebounce = null;

function showPanelUpdating(on) {
  const el = $("panel-updating");
  if (el) el.hidden = !on;
  const main = document.querySelector(".results-main");
  if (main) main.classList.toggle("is-refreshing", on);
}

function schedulePanelUpdate() {
  showPanelUpdating(true);
  clearTimeout(panelDebounce);
  panelDebounce = setTimeout(runPanelUpdate, 420);
}

function runPanelUpdate() {
  const rank = parseRankInput($("panel-rank"));
  if (rank === null) {
    showPanelUpdating(false);
    return;
  }
  // Mirror panel rank back to flow rank input
  if ($("kcet-rank")) $("kcet-rank").value = $("panel-rank").value;
  state.lastPayload = buildPayload();
  runLiveRequest(state.lastPayload);
}

async function executeRecommendationRequest(basePayload, { keepFilters = false } = {}) {
  const data = await apiRequest("/api/kcet/recommend", {
    method: "POST",
    body: JSON.stringify(basePayload),
  });
  state.totalByType = data.total_by_type || {};
  state.lastData = data;
  renderResults(data, { keepFilters });
  return data;
}

async function runLiveRequest(payload) {
  const seq = ++requestSeq;
  showPanelUpdating(true);
  try {
    await executeRecommendationRequest(payload, { keepFilters: true });
  } catch (err) {
    if (seq !== requestSeq) return;
    console.warn("Live update failed:", err && err.message);
  } finally {
    if (seq === requestSeq) showPanelUpdating(false);
  }
}

function syncPanelFromState() {
  if ($("panel-rank") && $("kcet-rank")) $("panel-rank").value = $("kcet-rank").value;
  syncQuotaRows();
  renderBranchGrids();
}

async function runRequest(payload, { keepFilters = false } = {}) {
  const seq = ++requestSeq;
  showView("loading");
  startLoadingLines();
  const minDelay = new Promise((r) => setTimeout(r, prefersReducedMotion ? 0 : 1100));

  try {
    await Promise.all([executeRecommendationRequest(payload, { keepFilters }), minDelay]);
    if (seq !== requestSeq) return;
    stopLoadingLines();
    sessionStorage.removeItem("disha_kcet_render_crash");
    syncPanelFromState();
    showView("results");
  } catch (err) {
    if (seq !== requestSeq) return;
    stopLoadingLines();
    $("error-message").textContent = err.message || "Something went wrong. Please try again.";
    showView("error");
  }
}

// ── Results rendering ───────────────────────────────────────────────────

function countUp(el, target) {
  if (!el) return;
  if (prefersReducedMotion || target === 0) {
    el.textContent = String(target);
    return;
  }
  const duration = 800;
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = String(Math.round(eased * target));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function renderProfileChips() {
  const p = state.lastPayload;
  const chips = [];
  chips.push(`KCET Rank <strong>${fmt(p.rank)}</strong>`);
  chips.push(escapeHtml(p.seat_category));
  for (const b of state.branchPrefs) chips.push(escapeHtml(branchLabel(b)));
  if (!state.branchPrefs.length) chips.push("All branches");

  $("profile-chips").innerHTML =
    chips.map((c) => `<span class="pchip">${c}</span>`).join("");
}

function noteHeadline(byCat, total) {
  if (total === 0) return "Try adjusting your rank, quota, or branch preferences.";
  if ((byCat.Target || 0) > 0 && (byCat.Safe || 0) > 0) return "You're standing in a good spot.";
  if ((byCat.Target || 0) > 0) return `${fmt(total)} realistic options found.`;
  if ((byCat.Safe || 0) > 0) return "You have strong backup options.";
  return "These are ambitious picks — worth trying.";
}

function updateStandingNoteUI() {
  const noteEl = $("spectrum-note");
  if (!noteEl) return;
  const thresholds = state.lastData?.thresholds || {};
  const safePct = Math.round((thresholds.safe_margin ?? 0.15) * 100);
  const dreamPct = Math.round((thresholds.upper_margin ?? 0.25) * 100);

  noteEl.innerHTML = `<strong>Safe:</strong> Your rank is well within the cutoff window (${safePct}% margin). &nbsp;
    <strong>Target:</strong> Your rank is close to the cutoff. &nbsp;
    <strong>Dream:</strong> Within ${dreamPct}% past the cutoff — ambitious but possible.`;
}

function renderNote(data) {
  const byCat = data.counts?.by_category || {};
  const total = data.counts?.total ?? 0;

  $("note-headline").textContent = noteHeadline(byCat, total);

  const pieces = [];
  if (data.guidance) pieces.push(data.guidance);
  $("note-guidance").textContent = pieces.join(" ");

  const tips = [];
  if (total > 0) {
    tips.push("KCET colleges offer lateral entry and branch changes after first year based on performance.");
    tips.push("Broad branches (CS, ECE, Mechanical, Civil) keep many doors open for future specialisation.");
    tips.push("Talk to current students and check NIRF rankings before finalising your choice.");
  }
  $("note-tips").innerHTML = tips
    .map((tip) => `<li>${escapeHtml(tip)}</li>`)
    .join("");

  const notesBox = $("api-notes");
  if (data.notes?.length) {
    notesBox.innerHTML = data.notes
      .map((n) => `<p class="api-note">${escapeHtml(n)}</p>`)
      .join("");
    notesBox.hidden = false;
  } else {
    notesBox.hidden = true;
    notesBox.innerHTML = "";
  }

  updateStandingNoteUI();
}

// ── Rank ruler ──────────────────────────────────────────────────────────

const RANK_AXIS_MAX = 200000;
const LOG_AXIS_MAX = Math.log10(RANK_AXIS_MAX);

function rankPos(rank) {
  const r = Math.min(Math.max(Number(rank) || 1, 1), RANK_AXIS_MAX);
  return Math.min(Math.max((Math.log10(r) / LOG_AXIS_MAX) * 100, 0.5), 99.5);
}

function rankPosScoped(rank, logMin, logMax) {
  const r = Math.min(Math.max(Number(rank) || 1, 1), RANK_AXIS_MAX);
  const logR = Math.log10(r);
  const span = logMax - logMin;
  if (span <= 0) return 50;
  return Math.min(Math.max(((logR - logMin) / span) * 100, 0.5), 99.5);
}

const ALL_TICKS = [
  { rank: 1, label: "1" },
  { rank: 5, label: "5" },
  { rank: 10, label: "10" },
  { rank: 50, label: "50" },
  { rank: 100, label: "100" },
  { rank: 500, label: "500" },
  { rank: 1000, label: "1K" },
  { rank: 2000, label: "2K" },
  { rank: 5000, label: "5K" },
  { rank: 10000, label: "10K" },
  { rank: 20000, label: "20K" },
  { rank: 50000, label: "50K" },
  { rank: 100000, label: "1L" },
  { rank: 200000, label: "2L" },
];

function ticksForRange(logMin, logMax) {
  const visible = ALL_TICKS.filter(t => {
    const logR = Math.log10(t.rank || 1);
    return logR >= logMin - 0.05 && logR <= logMax + 0.05;
  });
  if (visible.length > 8) return visible.filter((_, i) => i % 2 === 0);
  return visible;
}

const rulerZoomState = {};
const MIN_LOG_SPAN = 0.4;

function computeAutoRange(items, youRank) {
  const ranks = items.map(r => r.closing_rank);
  if (youRank) ranks.push(youRank);
  if (!ranks.length) return { logMin: 1, logMax: LOG_AXIS_MAX };
  const minR = Math.max(1, Math.min(...ranks));
  const maxR = Math.min(RANK_AXIS_MAX, Math.max(...ranks));
  const logMin = Math.log10(minR);
  const logMax = Math.log10(maxR);
  const padding = Math.max((logMax - logMin) * 0.15, 0.3);
  return {
    logMin: Math.max(0, logMin - padding),
    logMax: Math.min(LOG_AXIS_MAX, logMax + padding),
  };
}

function rulerGroupHtml(recs) {
  if (!recs.length) return "";
  const youRank = state.lastPayload?.rank;
  const getRank = (r) => r.closing_rank ?? Infinity;
  const sorted = recs.slice().sort((a, b) => getRank(a) - getRank(b));

  const gid = "kcet";
  const autoRange = computeAutoRange(recs, youRank);
  if (!rulerZoomState[gid]) {
    rulerZoomState[gid] = {
      logMin: autoRange.logMin, logMax: autoRange.logMax,
      defaultLogMin: autoRange.logMin, defaultLogMax: autoRange.logMax,
    };
  } else {
    rulerZoomState[gid].defaultLogMin = autoRange.logMin;
    rulerZoomState[gid].defaultLogMax = autoRange.logMax;
  }
  rulerZoomState[gid].dotLogs = sorted.map(r => Math.log10(r.closing_rank));
  const { logMin, logMax } = rulerZoomState[gid];

  const numLanes = 8;
  const lanes = [];
  for (let l = 0; l < numLanes; l++) lanes[l] = -100;

  const dots = sorted.map((r) => {
    const cat = r.category.toLowerCase();
    const absPos = Math.log10(r.closing_rank);
    let bestLane = 0;
    let maxDist = -1;
    for (let l = 0; l < numLanes; l++) {
      const dist = absPos - lanes[l];
      if (dist > maxDist) { maxDist = dist; bestLane = l; }
    }
    lanes[bestLane] = absPos;
    const topPct = 10 + (bestLane / (numLanes - 1)) * 80;
    const leftPct = rankPosScoped(r.closing_rank, logMin, logMax);
    return `<span class="ruler__dot ruler__dot--${cat}" style="left:${leftPct.toFixed(2)}%; top:${topPct.toFixed(2)}%" data-inst="${escapeHtml(r.institute)}" data-branch="${escapeHtml(r.program)}" data-rank="${r.closing_rank}" data-cat="${cat}"></span>`;
  }).join("");

  const visibleTicks = ticksForRange(logMin, logMax);
  const grid = visibleTicks.map(
    (tk) => `<span class="ruler__grid" style="left:${rankPosScoped(tk.rank, logMin, logMax).toFixed(2)}%"></span>`
  ).join("");
  const scale = visibleTicks.map(
    (tk) => `<span class="ruler__tick" style="left:${rankPosScoped(tk.rank, logMin, logMax).toFixed(2)}%">${tk.label}</span>`
  ).join("");

  const you = youRank
    ? `<div class="ruler__you" style="left:${rankPosScoped(youRank, logMin, logMax).toFixed(2)}%" title="Your rank: ${fmt(youRank)}"><span class="ruler__you-flag">YOU</span></div>`
    : "";

  const headRight = youRank
    ? `<span class="ruler__you-rank">YOU · ${fmt(youRank)}</span>`
    : `<span class="ruler__count">${recs.length} options</span>`;

  return `
    <div class="ruler__group" role="img" aria-label="KCET rank ruler: ${recs.length} options" data-ruler-id="${gid}">
      <div class="ruler__head">
        <span class="ruler__title">KCET Colleges <span class="ruler__via">via KCET 2025</span></span>
        ${headRight}
      </div>
      <div class="ruler__track-wrap">
        <div class="ruler__track" data-ruler-id="${gid}" tabindex="0" aria-label="Interactive chart track. Use arrow keys to pan, plus/minus to zoom.">
          ${grid}
          ${dots}
          ${you}
        </div>
        <div class="ruler__zoom-controls">
          <button type="button" class="ruler__zoom-btn" data-action="in" data-ruler-id="${gid}" title="Zoom in">+</button>
          <button type="button" class="ruler__zoom-btn" data-action="out" data-ruler-id="${gid}" title="Zoom out">−</button>
          <button type="button" class="ruler__zoom-btn" data-action="reset" data-ruler-id="${gid}" title="Reset zoom">⟲</button>
        </div>
      </div>
      <div class="ruler__scale">${scale}</div>
    </div>`;
}

function rerenderRulerGroup(rulerId) {
  const data = state.lastData;
  if (!data) return;
  const recs = data.recommendations || [];
  const groupEl = document.querySelector(`.ruler__group[data-ruler-id="${rulerId}"]`);
  if (!groupEl) return;
  const newHtml = rulerGroupHtml(recs);
  if (!newHtml) return;
  const temp = document.createElement("div");
  temp.innerHTML = newHtml;
  const newTrack = temp.querySelector('.ruler__track');
  const newScale = temp.querySelector('.ruler__scale');
  const oldTrack = groupEl.querySelector('.ruler__track');
  const oldScale = groupEl.querySelector('.ruler__scale');
  if (oldTrack && newTrack) oldTrack.innerHTML = newTrack.innerHTML;
  if (oldScale && newScale) oldScale.innerHTML = newScale.innerHTML;
}

function applyClampedRange(zs, newMin, newMax, action) {
  const minAllowed = 0;
  const maxAllowed = LOG_AXIS_MAX;
  const maxSpan = (zs.defaultLogMax || LOG_AXIS_MAX) - (zs.defaultLogMin || 0);
  let currentSpan = newMax - newMin;
  if (currentSpan > maxSpan) { const c = (newMin + newMax) / 2; newMin = c - maxSpan / 2; newMax = c + maxSpan / 2; }
  if (newMin < minAllowed) { newMax += (minAllowed - newMin); newMin = minAllowed; }
  if (newMax > maxAllowed) { newMin -= (newMax - maxAllowed); newMax = maxAllowed; }
  newMin = Math.max(minAllowed, newMin);
  newMax = Math.min(maxAllowed, newMax);
  if (newMax - newMin < 0.001) newMax = newMin + 0.001;
  zs.logMin = newMin;
  zs.logMax = newMax;
}

function applyZoom(rulerId, action) {
  const zs = rulerZoomState[rulerId];
  if (!zs) return;
  const span = zs.logMax - zs.logMin;
  if (action === "in") {
    const shrink = span * 0.15;
    if (span - shrink * 2 < MIN_LOG_SPAN) return;
    applyClampedRange(zs, zs.logMin + shrink, zs.logMax - shrink, "zoomIn");
  } else if (action === "out") {
    const grow = span * 0.2;
    applyClampedRange(zs, zs.logMin - grow, zs.logMax + grow, "zoomOut");
  } else if (action === "reset") {
    zs.logMin = zs.defaultLogMin;
    zs.logMax = zs.defaultLogMax;
  }
  rerenderRulerGroup(rulerId);
}

function applyPan(rulerId, deltaLog) {
  const zs = rulerZoomState[rulerId];
  if (!zs) return;
  applyClampedRange(zs, zs.logMin + deltaLog, zs.logMax + deltaLog, "pan");
  rerenderRulerGroup(rulerId);
}

function bindRulerZoom() {
  document.querySelectorAll(".ruler__zoom-btn").forEach(btn => {
    if (btn._zoomBound) return;
    btn._zoomBound = true;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      applyZoom(btn.dataset.rulerId, btn.dataset.action);
    });
  });
  document.querySelectorAll(".ruler__track").forEach(track => {
    if (track._wheelBound) return;
    track._wheelBound = true;
    track.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rulerId = track.dataset.rulerId;
      if (!rulerId) return;
      applyZoom(rulerId, e.deltaY < 0 ? "in" : "out");
    }, { passive: false });
  });
  document.querySelectorAll(".ruler__track").forEach(track => {
    if (track._keyBound) return;
    track._keyBound = true;
    track.addEventListener("keydown", (e) => {
      const rulerId = track.dataset.rulerId;
      if (!rulerId) return;
      const zs = rulerZoomState[rulerId];
      if (!zs) return;
      const span = zs.logMax - zs.logMin;
      if (e.key === "ArrowLeft") { e.preventDefault(); applyPan(rulerId, -span * 0.1); }
      if (e.key === "ArrowRight") { e.preventDefault(); applyPan(rulerId, span * 0.1); }
      if (e.key === "+" || e.key === "=") { e.preventDefault(); applyZoom(rulerId, "in"); }
      if (e.key === "-") { e.preventDefault(); applyZoom(rulerId, "out"); }
      if (e.key === "0") { e.preventDefault(); applyZoom(rulerId, "reset"); }
    });
  });
  document.querySelectorAll(".ruler__track").forEach(track => {
    if (track._dragBound) return;
    track._dragBound = true;
    let dragging = false, startX = 0, startLogMin = 0, startLogMax = 0;
    track.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".ruler__dot") || e.target.closest(".ruler__you")) return;
      const rulerId = track.dataset.rulerId;
      const zs = rulerZoomState[rulerId];
      if (!zs) return;
      dragging = true; startX = e.clientX; startLogMin = zs.logMin; startLogMax = zs.logMax;
      track.setPointerCapture(e.pointerId);
      track.style.cursor = "grabbing";
    });
    track.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const rulerId = track.dataset.rulerId;
      const zs = rulerZoomState[rulerId];
      if (!zs) return;
      const dx = e.clientX - startX;
      const trackWidth = track.offsetWidth || 1;
      const span = startLogMax - startLogMin;
      const deltaLog = -(dx / trackWidth) * span;
      applyClampedRange(zs, startLogMin + deltaLog, startLogMax + deltaLog, "pan");
      rerenderRulerGroup(rulerId);
    });
    const stopDrag = () => { dragging = false; track.style.cursor = ""; };
    track.addEventListener("pointerup", stopDrag);
    track.addEventListener("pointercancel", stopDrag);
  });
}

function renderRuler(data, keepZoom = false) {
  const el = $("ruler");
  const recs = data?.recommendations || [];
  if (!keepZoom) {
    for (const key of Object.keys(rulerZoomState)) delete rulerZoomState[key];
  }
  const groups = rulerGroupHtml(recs);

  if (!groups) {
    el.hidden = true; el.innerHTML = "";
    return;
  }

  el.innerHTML = `
    <div class="ruler__intro">
      <p class="eyebrow">Your rank on the map</p>
      <p class="ruler__lede">Each dot is a program. Your rank is the black line — dots to its left closed at a better rank than yours.</p>
    </div>
    ${groups}
    <div class="ruler__tip" id="ruler-tip" aria-hidden="true"></div>`;
  el.hidden = false;
  bindRulerZoom();
}

function bindRulerTooltip() {
  const el = $("ruler");
  const showTip = (dot) => {
    const tip = $("ruler-tip");
    if (!tip) return;
    const cr = el.getBoundingClientRect();
    const dr = dot.getBoundingClientRect();
    tip.innerHTML =
      `<strong>${escapeHtml(dot.dataset.inst)}</strong>` +
      `<span>${escapeHtml(dot.dataset.branch)}</span>` +
      `<em>Cutoff: ${fmt(Number(dot.dataset.rank))}</em>`;
    tip.dataset.cat = dot.dataset.cat;
    let leftPos = dr.left - cr.left + dr.width / 2;
    const tipWidth = tip.offsetWidth || 250;
    const minLeft = (tipWidth / 2) + 10;
    const maxLeft = cr.width - (tipWidth / 2) - 10;
    if (leftPos < minLeft) leftPos = minLeft;
    if (leftPos > maxLeft) leftPos = maxLeft;
    tip.style.left = `${leftPos}px`;
    tip.style.top = `${dr.top - cr.top}px`;
    tip.classList.add("is-on");
  };
  const hideTip = () => { const tip = $("ruler-tip"); if (tip) tip.classList.remove("is-on"); };
  el.addEventListener("pointerover", (e) => { const dot = e.target.closest(".ruler__dot"); if (dot) showTip(dot); });
  el.addEventListener("pointerout", (e) => { if (e.target.closest(".ruler__dot")) hideTip(); });
  el.addEventListener("click", (e) => {
    const dot = e.target.closest(".ruler__dot");
    if (dot) showTip(dot);
    else if (!e.target.closest(".ruler__zoom-btn")) hideTip();
  });
}

// ── Rank bar (single-cutoff adaptation) ──────────────────────────────────

function rankBarHtml(rec) {
  const cut = Math.round(rec.closing_rank);
  const rank = state.lastPayload.rank;
  // Create a synthetic window around the cutoff
  const bandWidth = Math.max(Math.round(cut * 0.15), 500);
  const syntheticOpen = Math.max(1, cut - bandWidth);
  const syntheticClose = cut;
  const span = Math.max(syntheticClose - syntheticOpen, 1);
  const trackLo = syntheticOpen - span * 0.45;
  const trackHi = syntheticClose + span * 0.45;
  const pos = (v) => ((v - trackLo) / (trackHi - trackLo)) * 100;

  const winLeft = pos(syntheticOpen);
  const winRight = pos(syntheticClose);
  const youPos = Math.min(Math.max(pos(rank), 3), 97);

  let verdict;
  if (rec.category === "Safe") {
    verdict = `Your rank (${fmt(rank)}) is better than the cutoff by ${fmt(Math.abs(cut - rank))} — very likely admission.`;
  } else if (rec.category === "Target") {
    if (rank <= cut) {
      verdict = `Your rank (${fmt(rank)}) is within the cutoff (${fmt(cut)}) — realistic chance.`;
    } else {
      verdict = `Cutoff (${fmt(cut)}) is ${fmt(rank - cut)} ranks above your rank — borderline.`;
    }
  } else {
    const gap = Math.abs(rank - cut);
    verdict = `Cutoff (${fmt(cut)}) is ${fmt(gap)} ranks from your rank — ambitious.`;
  }

  return `
    <div class="rankbar">
      <div class="rankbar__track">
        <div class="rankbar__window" style="left:${winLeft.toFixed(1)}%;right:${(100 - winRight).toFixed(1)}%"></div>
        <div class="rankbar__you" style="left:${youPos.toFixed(1)}%" title="Your rank: ${fmt(rank)}"></div>
      </div>
      <div class="rankbar__labels">
        <span>Cutoff <strong>${fmt(cut)}</strong></span>
        <span>Your rank <strong>${fmt(rank)}</strong></span>
      </div>
      <p class="rankbar__verdict">${escapeHtml(verdict)}</p>
    </div>`;
}

// ── Card components ─────────────────────────────────────────────────────

function confidenceChipHtml(rec) {
  const band = rec.confidence || "medium";
  let styleClass = "medium";
  let label = "Moderate";
  if (band === "high" || band === "highly_stable") { styleClass = "high"; label = "Steady"; }
  else if (band === "fragile" || band === "volatile_vacancy" || band === "volatile_erratic") { styleClass = "fragile"; label = "Variable"; }
  else { styleClass = "medium"; label = "Moderate"; }
  return `<span class="conf-chip conf-chip--${escapeHtml(styleClass)}" title="Cutoff confidence: ${escapeHtml(label)}">${escapeHtml(label)}</span>`;
}

function probabilityBadgeHtml(rec) {
  if (rec.admission_probability === null || rec.admission_probability === undefined) return "";
  const prob = rec.admission_probability;
  let probClass = "low";
  if (prob >= 75) probClass = "high";
  else if (prob >= 35) probClass = "medium";
  const text = `${Math.round(prob)}% chance`;
  return `<span class="tag tag--prob tag--prob-${probClass}" title="Estimated admission probability: ${Math.round(prob)}%">${escapeHtml(text)}</span>`;
}

function cardHtml(rec, index) {
  const cat = rec.category.toLowerCase();
  const delay = prefersReducedMotion ? 0 : Math.min(index * 45, 420);

  const foot = [
    rec.seat_category + " seat",
    "via KCET 2025",
    rec.degree || "",
  ].filter(Boolean);

  const reason = rec.reason
    ? `<p class="ccard__reason">${escapeHtml(rec.reason)}</p>`
    : "";

  const isBookmarked = state.choices && state.choices.some(c => c.institute === rec.institute && c.program === rec.program);
  const bookmarkHtml = `
    <button type="button" class="ccard__bookmark ${isBookmarked ? "is-selected" : ""}"
            data-institute="${escapeHtml(rec.institute)}"
            data-branch="${escapeHtml(rec.program)}"
            onclick="toggleBookmark(event, ${index}, '${escapeHtml(rec.institute).replace(/'/g, "\\'")}', '${escapeHtml(rec.program).replace(/'/g, "\\'")}')"
            aria-label="Add to preference list">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="bookmark-icon">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
      </svg>
    </button>`;

  return `
    <article class="ccard ccard--${cat}" style="animation-delay:${delay}ms">
      ${bookmarkHtml}
      <div class="ccard__meta">
        <span class="tag tag--private">PRIVATE</span>
        <span class="tag">KARNATAKA</span>
        ${probabilityBadgeHtml(rec)}
        ${confidenceChipHtml(rec)}
      </div>
      <h3 class="ccard__institute">${escapeHtml(rec.institute)}</h3>
      <p class="ccard__branch">${escapeHtml(rec.program)}</p>
      ${rankBarHtml(rec)}
      ${reason}
      <div class="ccard__foot">${foot.map((f) => `<span>${escapeHtml(f)}</span>`).join("")}</div>
    </article>`;
}

// ── College-grouped card (by-college view) ──────────────────────────────

function getCollegeLocation(rec) {
  const parts = rec.institute.split(",");
  if (parts.length > 1) return parts[parts.length - 1].trim();
  return "Karnataka";
}

function getCollegeDomId(instName) {
  return "college-" + instName.toLowerCase().replace(/[^a-z0-9]/g, "-");
}

window.toggleCollegeCard = function (event, instName) {
  if (event) { event.preventDefault(); event.stopPropagation(); }
  const isExpanded = !state.expandedColleges[instName];
  state.expandedColleges[instName] = isExpanded;
  const domId = getCollegeDomId(instName);
  const collapseEl = document.getElementById(`collapse-${domId}`);
  const headerEl = collapseEl ? collapseEl.previousElementSibling : null;
  if (collapseEl && headerEl) {
    collapseEl.hidden = !isExpanded;
    headerEl.classList.toggle("is-expanded", isExpanded);
  }
};

function branchRowCardHtml(r, index) {
  const cat = r.category.toLowerCase();
  const delay = prefersReducedMotion ? 0 : Math.min(index * 45, 420);
  const foot = [r.seat_category + " seat", r.degree || ""].filter(Boolean);
  const reason = r.reason ? `<p class="ccard__reason">${escapeHtml(r.reason)}</p>` : "";

  const isBookmarked = state.choices && state.choices.some(c => c.institute === r.institute && c.program === r.program);
  const bookmarkHtml = `
    <button type="button" class="ccard__bookmark ${isBookmarked ? "is-selected" : ""}"
            data-institute="${escapeHtml(r.institute)}"
            data-branch="${escapeHtml(r.program)}"
            onclick="toggleBookmark(event, ${index}, '${escapeHtml(r.institute).replace(/'/g, "\\'")}', '${escapeHtml(r.program).replace(/'/g, "\\'")}')"
            aria-label="Add to preference list">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="bookmark-icon">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
      </svg>
    </button>`;

  return `
    <article class="ccard ccard--${cat} ccard--subbranch" style="animation-delay:${delay}ms; margin-top: 10px; box-shadow: none; border-color: var(--line);">
      ${bookmarkHtml}
      <div class="ccard__meta">
        ${probabilityBadgeHtml(r)}
        ${confidenceChipHtml(r)}
      </div>
      <p class="ccard__branch" style="font-size: 0.95rem; font-weight: 600; margin-top: 4px;">${escapeHtml(r.program)}</p>
      ${rankBarHtml(r)}
      ${reason}
      <div class="ccard__foot">${foot.map((f) => `<span>${escapeHtml(f)}</span>`).join("")}</div>
    </article>`;
}

function collegeCardHtml(group, catName, index) {
  const firstRec = group.branches[0];
  const instName = group.institute;
  const city = getCollegeLocation(firstRec);
  const branchCount = group.branches.length;
  const isExpanded = !!state.expandedColleges[instName];
  const catClass = catName.toLowerCase();
  const delay = prefersReducedMotion ? 0 : Math.min(index * 45, 420);
  const domId = getCollegeDomId(instName);

  const branchRowsHtml = group.branches.map((r, bIdx) => {
    return branchRowCardHtml(r, index * 100 + bIdx);
  }).join("");

  return `
    <article class="ccard ccard--${catClass} ccard--college" style="animation-delay:${delay}ms">
      <div class="ccard__college-header ${isExpanded ? "is-expanded" : ""}" onclick="toggleCollegeCard(event, '${escapeHtml(instName).replace(/'/g, "\\'")}')"">
        <div class="ccard__meta" style="width: 100%;">
          <span class="tag tag--private">PRIVATE</span>
          <span class="tag">KARNATAKA</span>
          <span class="tag tag--count" style="margin-left: auto; background: var(--paper-deep); color: var(--ink-soft); font-weight: 600;">${branchCount} ${branchCount === 1 ? 'branch' : 'branches'}</span>
        </div>
        <div class="ccard__college-title-row" style="margin-top: 10px; display: flex; justify-content: space-between; align-items: flex-start; width: 100%; gap: 12px;">
          <h3 class="ccard__institute" style="margin: 0; font-size: 1.12rem;">${escapeHtml(instName)} <small style="font-size: 0.82rem; font-weight: 500; color: var(--ink-soft); display: inline-block; margin-left: 6px;">(${escapeHtml(city)})</small></h3>
          <svg class="chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" style="transition: transform 0.2s; margin-top: 5px; flex-shrink: 0;"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
      </div>
      <div class="ccard__branches-collapse" id="collapse-${domId}" ${isExpanded ? "" : "hidden"}>
        <div class="ccard__branches-list" style="margin-top: 14px; border-top: 1px solid var(--line); padding-top: 6px;">
          ${branchRowsHtml}
        </div>
      </div>
    </article>
  `;
}

// ── Choice List / Bookmarking ──────────────────────────────────────────

window.toggleBookmark = function (event, index, institute, branch) {
  if (event) { event.preventDefault(); event.stopPropagation(); }
  const idx = state.choices.findIndex(c => c.institute === institute && c.program === branch);
  if (idx > -1) {
    state.choices.splice(idx, 1);
  } else {
    const recommendations = state.lastData?.recommendations || [];
    const rec = recommendations.find(r => r.institute === institute && r.program === branch);
    if (!rec) return;
    state.choices.push({
      institute: rec.institute, branch: rec.program, degree: rec.degree,
      seat_category: rec.seat_category, closing_rank: rec.closing_rank, category: rec.category,
      fit_label: rec.fit_label, program: rec.program,
    });
  }
  localStorage.setItem("disha_kcet_choices", JSON.stringify(state.choices));
  updateChoiceUI();
};

window.moveChoice = function (index, direction) {
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= state.choices.length) return;
  const temp = state.choices[index];
  state.choices[index] = state.choices[targetIndex];
  state.choices[targetIndex] = temp;
  localStorage.setItem("disha_kcet_choices", JSON.stringify(state.choices));
  updateChoiceUI();
};

function updateChoiceUI() {
  const trigger = $("choice-list-trigger");
  const count = $("choice-count");
  const clearBtn = $("choice-clear-all");

  if (count) count.textContent = state.choices.length;
  if (clearBtn) clearBtn.style.display = state.choices.length > 0 ? "inline-block" : "none";

  const inResultsView = $("view-results")?.classList.contains("is-active");
  if (trigger) trigger.style.display = (inResultsView && state.choices.length > 0) ? "flex" : "none";

  document.querySelectorAll(".ccard__bookmark").forEach(btn => {
    const inst = btn.dataset.institute;
    const br = btn.dataset.branch;
    const bookmarked = state.choices.some(c => c.institute === inst && c.program === br);
    btn.classList.toggle("is-selected", bookmarked);
  });
  renderChoiceDrawerList();
}

let draggedIndex = null;

function renderChoiceDrawerList() {
  const list = $("choice-drawer-list");
  if (!list) return;
  list.innerHTML = "";
  if (state.choices.length === 0) {
    list.innerHTML = `<li class="choice-drawer__empty">No choices selected. Tap the bookmark icon on any recommendation card to build your preference list.</li>`;
    return;
  }
  state.choices.forEach((c, idx) => {
    const li = document.createElement("li");
    li.className = "choice-drawer__item";
    li.draggable = true;
    li.dataset.index = idx;
    li.innerHTML = `
      <div class="choice-drawer__actions">
        <button type="button" class="choice-drawer__action-btn choice-drawer__action-btn--up" onclick="moveChoice(${idx}, -1)" aria-label="Move Up" ${idx === 0 ? "disabled" : ""}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="18 15 12 9 6 15"/></svg>
        </button>
        <button type="button" class="choice-drawer__action-btn choice-drawer__action-btn--down" onclick="moveChoice(${idx}, 1)" aria-label="Move Down" ${idx === state.choices.length - 1 ? "disabled" : ""}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
      </div>
      <div class="choice-drawer__item-info">
        <span class="choice-drawer__item-rank">#${idx + 1}</span>
        <div>
          <strong class="choice-drawer__item-inst">${escapeHtml(c.institute || "")}</strong>
          <span class="choice-drawer__item-branch">${escapeHtml(c.program || "")}</span>
        </div>
      </div>
      <button type="button" class="choice-drawer__item-remove" onclick="toggleBookmark(event, null, '${escapeHtml(c.institute || "").replace(/'/g, "\\'")}', '${escapeHtml(c.program || "").replace(/'/g, "\\'")}')">&times;</button>
    `;
    li.addEventListener("dragstart", (e) => { draggedIndex = idx; li.classList.add("is-dragging"); e.dataTransfer.effectAllowed = "move"; });
    li.addEventListener("dragend", () => { li.classList.remove("is-dragging"); draggedIndex = null; });
    li.addEventListener("dragover", (e) => { e.preventDefault(); li.classList.add("is-dragover"); });
    li.addEventListener("dragleave", () => { li.classList.remove("is-dragover"); });
    li.addEventListener("drop", (e) => {
      e.preventDefault(); li.classList.remove("is-dragover");
      if (draggedIndex === null || draggedIndex === idx) return;
      const moved = state.choices.splice(draggedIndex, 1)[0];
      state.choices.splice(idx, 0, moved);
      localStorage.setItem("disha_kcet_choices", JSON.stringify(state.choices));
      updateChoiceUI();
    });
    list.appendChild(li);
  });
}

window.clearChoices = function () {
  if (state.choices.length === 0) return;
  if (confirm("Are you sure you want to clear your entire preference list?")) {
    state.choices = [];
    localStorage.setItem("disha_kcet_choices", JSON.stringify(state.choices));
    updateChoiceUI();
    $("choice-drawer").hidden = true;
  }
};

function exportChoicesCSV() {
  if (state.choices.length === 0) return;
  let csv = "Preference Number,Institute,Branch,Degree,Category\n";
  state.choices.forEach((c, idx) => {
    csv += `${idx + 1},"${(c.institute || "").replace(/"/g, '""')}","${(c.program || "").replace(/"/g, '""')}","${(c.degree || "").replace(/"/g, '""')}","${c.category || ""}"\n`;
  });
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", "my_disha_kcet_choices.csv");
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function printChoices() {
  if (state.choices.length === 0) return;
  const printWindow = window.open("", "_blank");
  if (!printWindow) { alert("Please allow popups to print your preference list."); return; }
  let rowsHtml = state.choices.map((c, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td><strong>${escapeHtml(c.institute || "")}</strong></td>
      <td>${escapeHtml(c.program || "")}</td>
      <td>${escapeHtml(c.degree || "")}</td>
    </tr>
  `).join("");
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>My Disha KCET Preference List</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #333; padding: 40px; }
        h1 { margin-bottom: 8px; color: #111; }
        p { color: #666; font-size: 14px; margin-bottom: 24px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #e0e0e0; padding: 12px 16px; text-align: left; }
        th { background-color: #f7f7f7; font-weight: 600; }
        tr:nth-child(even) { background-color: #fafafa; }
        @media print { body { padding: 0; } button { display: none; } }
      </style>
    </head>
    <body>
      <h1>UTMT Disha - My KCET Preference List</h1>
      <p>Customized KCET college choices generated on ${new Date().toLocaleDateString()}.</p>
      <table>
        <thead><tr><th style="width: 60px;">Pref #</th><th>Institute</th><th>Branch</th><th>Degree</th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
      <script>window.onload = function() { window.print(); setTimeout(function() { window.close(); }, 500); };<\/script>
    </body>
    </html>
  `);
  printWindow.document.close();
}

// ── Filtering ──────────────────────────────────────────────────────────

function recPassesFilters(rec) {
  if (!state.filterText) return true;
  const q = state.filterText;
  return (
    rec.institute.toLowerCase().includes(q) ||
    (rec.program || "").toLowerCase().includes(q) ||
    (rec.program || "").toLowerCase().includes(q)
  );
}

// ── View toggle (by-branch / by-college) ────────────────────────────────

function syncViewToggleUI() {
  const btnBranch = $("view-by-branch");
  const btnCollege = $("view-by-college");
  if (btnBranch && btnCollege) {
    btnBranch.classList.toggle("is-active", state.view === "branch");
    btnCollege.classList.toggle("is-active", state.view === "college");
  }
}

// ── Section rendering ──────────────────────────────────────────────────

function renderSections() {
  const data = state.lastData;
  const container = $("result-sections");
  container.innerHTML = "";

  const blurbs = {};
  for (const cg of data?.category_guidance || []) blurbs[cg.category] = cg.blurb;

  let anyShown = false;

  for (const catName of SECTION_ORDER) {
    const all = (data?.recommendations || []).filter((r) => r.category === catName);
    if (all.length === 0) continue;
    const visible = all.filter(recPassesFilters);

    anyShown = true;

    const meta = sectionMeta(catName);
    const section = document.createElement("section");
    section.className = "rsection";
    section.id = `section-${catName.toLowerCase()}`;

    const sortedVisible = [...visible];
    if (state.sortBy === "probability") {
      sortedVisible.sort((a, b) => {
        const valA = a.admission_probability ?? 0;
        const valB = b.admission_probability ?? 0;
        return valB - valA;
      });
    } else if (state.sortBy === "rank") {
      sortedVisible.sort((a, b) => {
        const valA = a.closing_rank ?? Infinity;
        const valB = b.closing_rank ?? Infinity;
        return valA - valB;
      });
    } else if (state.sortBy === "college") {
      sortedVisible.sort((a, b) => (a.institute || "").localeCompare(b.institute || ""));
    }

    let contentHtml = "";
    if (state.view === "college") {
      const grouped = [];
      visible.forEach((r) => {
        let group = grouped.find((g) => g.institute === r.institute);
        if (!group) { group = { institute: r.institute, branches: [] }; grouped.push(group); }
        group.branches.push(r);
      });

      if (state.sortBy === "probability") {
        grouped.sort((a, b) => {
          const maxA = Math.max(...a.branches.map(r => r.admission_probability ?? 0), 0);
          const maxB = Math.max(...b.branches.map(r => r.admission_probability ?? 0), 0);
          return maxB - maxA;
        });
      } else if (state.sortBy === "rank") {
        grouped.sort((a, b) => {
          const minA = Math.min(...a.branches.map(r => r.closing_rank ?? Infinity), Infinity);
          const minB = Math.min(...b.branches.map(r => r.closing_rank ?? Infinity), Infinity);
          return minA - minB;
        });
      } else if (state.sortBy === "college") {
        grouped.sort((a, b) => a.institute.localeCompare(b.institute));
      }

      grouped.forEach((group) => {
        if (state.sortBy === "rank") group.branches.sort((a, b) => (a.closing_rank ?? Infinity) - (b.closing_rank ?? Infinity));
        else if (state.sortBy === "probability") group.branches.sort((a, b) => (b.admission_probability ?? 0) - (a.admission_probability ?? 0));
        else if (state.sortBy === "college") group.branches.sort((a, b) => (a.branch || "").localeCompare(b.branch || ""));
      });

      const CARD_LIMIT = 25;
      const showAllC = !!state.showAllCards?.[catName];
      const collegeSlice = showAllC ? grouped : grouped.slice(0, CARD_LIMIT);
      contentHtml = `<div class="cards">${collegeSlice.map((g, i) => collegeCardHtml(g, catName, i)).join("")}</div>`;
      if (!showAllC && grouped.length > CARD_LIMIT) {
        const rem = grouped.length - CARD_LIMIT;
        contentHtml += `<div style="text-align:center;margin:20px 0 8px"><button type="button" class="btn btn--ghost" onclick="showMoreCards('${catName}')" style="gap:6px;font-size:.92rem">Show ${rem} more colleges ▾</button></div>`;
      }
    } else {
      const CARD_LIMIT = 25;
      const showAllB = !!state.showAllCards?.[catName];
      const branchSlice = showAllB ? sortedVisible : sortedVisible.slice(0, CARD_LIMIT);
      contentHtml = `<div class="cards">${branchSlice.map((r, i) => cardHtml(r, i)).join("")}</div>`;
      if (!showAllB && sortedVisible.length > CARD_LIMIT) {
        const rem = sortedVisible.length - CARD_LIMIT;
        contentHtml += `<div style="text-align:center;margin:20px 0 8px"><button type="button" class="btn btn--ghost" onclick="showMoreCards('${catName}')" style="gap:6px;font-size:.92rem">Show ${rem} more options ▾</button></div>`;
      }
    }

    const totalAvail = all.length;
    const isSectionCollapsed = !!state.collapsedSections[catName];
    section.innerHTML = `
      <div class="rsection__head">
        <h2 class="rsection__title">
          <span class="dot dot--${catName.toLowerCase()}" aria-hidden="true"></span>
          ${meta.title} <span class="rsection__count">· ${meta.sub} · Showing ${visible.length} of ${totalAvail}</span>
        </h2>
        <button type="button" class="rsection__toggle-btn" 
                aria-expanded="${!isSectionCollapsed}" 
                aria-controls="cards-${catName.toLowerCase()}" 
                onclick="toggleSection('${catName}')">
          <span class="rsection__toggle-text">${isSectionCollapsed ? "Expand" : "Collapse"}</span>
          <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      </div>
      <div class="rsection__collapse ${isSectionCollapsed ? "is-collapsed" : ""}" id="cards-${catName.toLowerCase()}">
        <div class="rsection__collapse-inner">
          ${blurbs[catName] ? `<p class="rsection__blurb">${escapeHtml(blurbs[catName])}</p>` : ""}
          ${contentHtml}
        </div>
      </div>`;
    container.appendChild(section);
  }

  updateExpandAllButtonUI();

  const totalAllCount = (data?.recommendations || []).length;
  const hasResults = totalAllCount > 0;
  $("empty-results").hidden = hasResults;
  $("empty-filtered").hidden = !hasResults || anyShown;
  $("toolbar").style.display = hasResults ? "" : "none";
  $("spectrum").style.display = hasResults ? "" : "none";
  const specHeader = $("spectrum-header");
  if (specHeader) specHeader.style.display = hasResults ? "flex" : "none";
}

window.showMoreCards = function (catName) {
  if (!state.showAllCards) state.showAllCards = {};
  state.showAllCards[catName] = true;
  renderSections();
};

window.toggleSection = function (catName) {
  state.collapsedSections[catName] = !state.collapsedSections[catName];
  const sectionEl = $(`section-${catName.toLowerCase()}`);
  if (sectionEl) {
    const btn = sectionEl.querySelector(".rsection__toggle-btn");
    const collapseEl = sectionEl.querySelector(".rsection__collapse");
    if (btn && collapseEl) {
      const isExpanded = !state.collapsedSections[catName];
      btn.setAttribute("aria-expanded", String(isExpanded));
      collapseEl.classList.toggle("is-collapsed", !isExpanded);
      const textEl = btn.querySelector(".rsection__toggle-text");
      if (textEl) textEl.textContent = isExpanded ? "Collapse" : "Expand";
    }
  }
  updateExpandAllButtonUI();
};

window.updateExpandAllButtonUI = function () {
  const btns = document.querySelectorAll(".expand-collapse-all-btn");
  if (btns.length === 0) return;
  const data = state.lastData;
  const recs = data?.recommendations || [];
  let hasAnyExpanded = false;
  for (const catName of SECTION_ORDER) {
    const all = recs.filter((r) => r.category === catName);
    if (all.length === 0) continue;
    const visible = all.filter(recPassesFilters);
    if (visible.length === 0) continue;
    if (!state.collapsedSections[catName]) { hasAnyExpanded = true; break; }
  }
  btns.forEach(btn => {
    btn.textContent = hasAnyExpanded ? "Collapse all" : "Expand all";
    btn.dataset.action = hasAnyExpanded ? "collapse" : "expand";
  });
};

function buildSortOptions() {
  const sortSel = $("results-sort");
  if (!sortSel) return;
  const prev = sortSel.value || state.sortBy || "rank";
  sortSel.innerHTML = "";
  const options = [
    { value: "rank", label: "Sort by cutoff rank" },
    { value: "probability", label: "Sort by probability" },
    { value: "college", label: "Sort by college name" },
  ];
  options.forEach((opt) => {
    const el = document.createElement("option");
    el.value = opt.value;
    el.textContent = opt.label;
    sortSel.appendChild(el);
  });
  sortSel.value = prev;
}

function renderResults(data, { keepFilters = false } = {}) {
  if (!keepFilters) {
    state.filterText = "";
    state.sortBy = "rank";
    state.collapsedSections = { Safe: false, Target: false, Reach: false };
    state.expandedColleges = {};
    state.showAllCards = {};
    $("filter-search").value = "";
  }

  buildSortOptions();
  renderProfileChips();
  renderNote(data);
  renderRuler(data, keepFilters);

  const byCat = data.counts?.by_category || {};
  countUp($("zone-count-safe"), byCat.Safe || 0);
  countUp($("zone-count-target"), byCat.Target || 0);
  countUp($("zone-count-reach"), byCat.Reach || 0);
  document.querySelectorAll(".zone").forEach((z) => {
    z.classList.toggle("is-empty", !(byCat[z.dataset.zone] > 0));
  });

  syncViewToggleUI();
  renderSections();
  updateChoiceUI();
}

// ── Share / copy link / print ─────────────────────────────────────────────

function buildShareUrl() {
  const params = new URLSearchParams();

  let currentStep = "welcome";
  if ($("view-results")?.classList.contains("is-active")) {
    currentStep = "results";
  } else if ($("view-flow")?.classList.contains("is-active")) {
    currentStep = String(state.step);
  }
  params.set("step", currentStep);

  const rank = parseRankInput($("kcet-rank"));
  if (rank !== null) params.set("r", String(rank));
  params.set("c", state.seat_category);
  if (state.branchPrefs && state.branchPrefs.length) {
    params.set("b", state.branchPrefs.join(","));
  }
  if (state.filterText) params.set("search", state.filterText);

  const base = `${location.origin}${location.pathname}`;
  return `${base}?${params.toString()}`;
}

function saveStateToURL() {
  if (!initialStateLoaded) return;
  const newUrl = buildShareUrl();
  history.replaceState(null, "", newUrl);
}

function loadStateFromURL() {
  const q = new URLSearchParams(location.search);
  const hasParams = [...q.keys()].length > 0;
  if (!hasParams) { initialStateLoaded = true; return false; }

  // Restore rank
  const rank = parseInt(q.get("r") || "", 10);
  const hasRank = Number.isFinite(rank) && rank > 0;
  if (hasRank) $("kcet-rank").value = fmt(rank);

  // Restore quota
  const quota = q.get("c");
  if (quota) {
    state.seat_category = quota;
    syncQuotaRows();
  }

  // Restore branch preferences
  const valid = new Set(branchOptions().map((o) => o.value));
  state.branchPrefs = (q.get("b") || "")
    .split(",")
    .map((v) => v.trim())
    .filter((v) => valid.has(v));
  renderBranchGrids();

  // Restore filter text
  const filterText = q.get("search") || "";
  state.filterText = filterText.toLowerCase();
  $("filter-search").value = filterText;

  syncPanelFromState();

  const stepParam = q.get("step");
  if (stepParam === "results" || (!stepParam && hasRank)) {
    const _crashKey = "disha_kcet_render_crash";
    const _prevCrashes = parseInt(sessionStorage.getItem(_crashKey) || "0", 10);
    sessionStorage.setItem(_crashKey, String(_prevCrashes + 1));
    const payload = buildPayload();
    state.lastPayload = payload;
    runRequest(payload, { keepFilters: true }).then(() => {
      sessionStorage.removeItem("disha_kcet_render_crash");
    });
  } else {
    const stepNum = parseInt(stepParam, 10);
    if (Number.isInteger(stepNum) && stepNum >= 0 && stepNum < TOTAL_STEPS) {
      showView("flow");
      goToStep(stepNum);
    } else {
      showView("welcome");
    }
  }
  initialStateLoaded = true;
  return true;
}

function shareToWhatsApp() {
  const counts = state.lastData?.counts?.by_category || {};
  const rank = state.lastPayload?.rank;
  const text = `My KCET rank ${fmt(rank)} (${state.seat_category}). Found ${counts.Target || 0} Target, ${counts.Safe || 0} Safe and ${counts.Reach || 0} Dream options!\n\nCheck out Disha for free KCET college predictions:\n${buildShareUrl()}`;
  window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
}

async function copyShareLink() {
  const url = buildShareUrl();
  const label = $("copy-link-label");
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(url);
    } else {
      const ta = document.createElement("textarea");
      ta.value = url; ta.setAttribute("readonly", "");
      ta.style.position = "absolute"; ta.style.left = "-9999px";
      document.body.appendChild(ta); ta.select();
      document.execCommand("copy"); document.body.removeChild(ta);
    }
    label.textContent = "Copied!";
    setTimeout(() => { label.textContent = "Copy link"; }, 1800);
  } catch {
    label.textContent = "Copy link";
    alert("Failed to copy link. Please copy the URL manually.");
  }
}

// ── Panel events ────────────────────────────────────────────────────────

function bindPanelEvents() {
  const toggle = $("panel-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const panel = $("results-panel");
      const open = panel.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  const tbToggle = $("toolbar-toggle");
  if (tbToggle) {
    tbToggle.addEventListener("click", () => {
      const tb = $("toolbar");
      const open = tb.classList.toggle("is-open");
      tbToggle.setAttribute("aria-expanded", open ? "true" : "false");
      if (tb) delete tb.dataset.autoOpened;
    });
  }

  window.addEventListener("scroll", () => {
    if (window.innerWidth <= 900) {
      const tb = $("toolbar");
      const tbToggle = $("toolbar-toggle");
      if (tb && tb.classList.contains("is-open")) {
        if (window.scrollY > 150 && tb.dataset.autoOpened === "true") {
          tb.classList.remove("is-open");
          if (tbToggle) tbToggle.setAttribute("aria-expanded", "false");
          delete tb.dataset.autoOpened;
        }
      }
    }
  });

  const panelRank = $("panel-rank");
  if (panelRank) {
    attachRankFormatting(panelRank);
    panelRank.addEventListener("input", () => {
      const n = parseRankInput(panelRank);
      if ($("kcet-rank")) $("kcet-rank").value = panelRank.value;
      schedulePanelUpdate();
    });
  }

  bindQuotaRow("panel-seat_category-row", schedulePanelUpdate);
}

// ── Events ──────────────────────────────────────────────────────────────

function bindEvents() {
  $("begin-btn").addEventListener("click", () => {
    showView("flow");
    goToStep(0);
  });

  $("retry-meta-btn")?.addEventListener("click", loadMeta);

  $("flow-form").addEventListener("submit", (e) => {
    e.preventDefault();
    advanceStep();
  });

  $("flow-back").addEventListener("click", () => {
    if (state.step > 0) goToStep(state.step - 1, { backwards: true });
  });

  $("restart-btn").addEventListener("click", () => {
    state.expandedColleges = {};
    showView("welcome");
  });
  $("wordmark")?.addEventListener("click", (e) => {
    e.preventDefault();
    state.expandedColleges = {};
    showView("welcome");
  });

  $("retry-btn").addEventListener("click", () => {
    if (state.lastPayload) runRequest(state.lastPayload);
  });

  const backToReview = () => {
    showView("flow");
    goToStep(TOTAL_STEPS - 1, { backwards: true });
  };
  $("error-edit-btn").addEventListener("click", backToReview);
  $("edit-profile-btn").addEventListener("click", backToReview);
  $("empty-edit-btn")?.addEventListener("click", backToReview);

  bindQuotaRow("seat_category-row");
  bindPanelEvents();

  // Choice drawer
  $("choice-list-trigger")?.addEventListener("click", () => {
    $("choice-drawer").hidden = false;
    renderChoiceDrawerList();
  });
  $("choice-drawer-close")?.addEventListener("click", () => { $("choice-drawer").hidden = true; });
  $("choice-drawer-overlay")?.addEventListener("click", () => { $("choice-drawer").hidden = true; });
  $("choice-export-csv")?.addEventListener("click", exportChoicesCSV);
  $("choice-export-pdf")?.addEventListener("click", printChoices);
  $("choice-clear-all")?.addEventListener("click", clearChoices);

  // Search
  $("filter-search").addEventListener("input", (e) => {
    state.filterText = e.target.value.trim().toLowerCase();
    renderSections();
    saveStateToURL();
  });

  $("clear-filters-btn")?.addEventListener("click", () => {
    state.filterText = "";
    $("filter-search").value = "";
    renderSections();
    saveStateToURL();
  });

  // Expand/collapse all
  const expColAllBtns = document.querySelectorAll(".expand-collapse-all-btn");
  expColAllBtns.forEach(btnEl => {
    btnEl.addEventListener("click", () => {
      const action = btnEl.dataset.action || "collapse";
      const shouldCollapse = action === "collapse";
      for (const catName of SECTION_ORDER) {
        state.collapsedSections[catName] = shouldCollapse;
        const sectionEl = $(`section-${catName.toLowerCase()}`);
        if (sectionEl) {
          const btn = sectionEl.querySelector(".rsection__toggle-btn");
          const collapseEl = sectionEl.querySelector(".rsection__collapse");
          if (btn && collapseEl) {
            btn.setAttribute("aria-expanded", String(!shouldCollapse));
            collapseEl.classList.toggle("is-collapsed", shouldCollapse);
            const textEl = btn.querySelector(".rsection__toggle-text");
            if (textEl) textEl.textContent = shouldCollapse ? "Expand" : "Collapse";
          }
        }
      }
      updateExpandAllButtonUI();
    });
  });

  // View toggle (by-branch / by-college)
  const btnBranch = $("view-by-branch");
  const btnCollege = $("view-by-college");
  if (btnBranch && btnCollege) {
    btnBranch.addEventListener("click", () => {
      if (state.view !== "branch") {
        state.view = "branch";
        localStorage.setItem("disha_kcet_view", "branch");
        syncViewToggleUI();
        renderSections();
      }
    });
    btnCollege.addEventListener("click", () => {
      if (state.view !== "college") {
        state.view = "college";
        localStorage.setItem("disha_kcet_view", "college");
        syncViewToggleUI();
        renderSections();
      }
    });
  }

  // Sort
  const sortSel = $("results-sort");
  if (sortSel) {
    sortSel.addEventListener("change", (e) => {
      state.sortBy = e.target.value;
      renderSections();
    });
  }

  // Spectrum scroll-to-section
  $("spectrum")?.addEventListener("click", (e) => {
    const zone = e.target.closest(".zone");
    if (!zone) return;
    const target = $(`section-${zone.dataset.zone.toLowerCase()}`);
    if (target) target.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "start" });
  });

  // Share / Copy / Print
  $("share-btn").addEventListener("click", shareToWhatsApp);
  $("copy-link-btn").addEventListener("click", copyShareLink);
  $("print-btn").addEventListener("click", () => {
    if (state.filterText) {
      state.filterText = "";
      $("filter-search").value = "";
      renderSections();
    }
    window.print();
  });
}

// ── Init ────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  attachRankFormatting($("kcet-rank"));
  bindEvents();
  bindRulerTooltip();

  window.addEventListener("beforeunload", () => {
    sessionStorage.setItem("disha_kcet_scroll_y", String(window.scrollY));
  });

  const hasParams = [...new URLSearchParams(location.search).keys()].length > 0;

  const _crashCount = parseInt(sessionStorage.getItem("disha_kcet_render_crash") || "0", 10);
  let skipUrlRestore = false;
  if (hasParams && _crashCount >= 2) {
    console.warn("Disha KCET: detected crash loop — resetting to welcome view.");
    sessionStorage.removeItem("disha_kcet_render_crash");
    history.replaceState(null, "", location.pathname);
    skipUrlRestore = true;
  }

  if (hasParams && !skipUrlRestore) {
    showView("loading");
  } else {
    showView("welcome");
  }

  loadMeta().then(() => {
    if (skipUrlRestore) { showView("welcome"); return; }
    const restored = loadStateFromURL();
    if (!restored) showView("welcome");
  });
});
