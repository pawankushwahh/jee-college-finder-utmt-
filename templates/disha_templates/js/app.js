"use strict";

/* ════════════════════════════════════════════════════════════════════════
   Disha — app logic
   Views: welcome → guided 5-step flow → loading → results (or error).
   Talks to the FastAPI backend via fetchMeta() / fetchRecommendations()
   defined in api.js.
   ════════════════════════════════════════════════════════════════════════ */

// ── Static content ──────────────────────────────────────────────────────
// User-facing strings live in js/i18n.js (en{} / hi{}) and are pulled via t().
// Only the language-independent SVG icons + ordering live here.

const GOAL_ICONS = {
  coding: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  research: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg>',
  pure_science: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v8L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45L14 10V2z"/><path d="M8.5 2h7"/><path d="M7 16h10"/></svg>',
  mba: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>',
  core: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
  undecided: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
};

const GOAL_IDS = ["coding", "research", "pure_science", "mba", "core", "undecided"];

const QUOTA_KEYS = ["AI", "HS", "OS", "GO", "JK", "LA"];
const quotaLabel = (q) => (QUOTA_KEYS.includes(q) ? t(`quota.${q}`) : q);

const goalName = (id) => t(`goals.${id}.name`);
const goalTips = (id) => t(`goalTips.${id}`) || [];

const SECTION_ORDER = ["Target", "Reach", "Safe"];
const sectionMeta = (cat) => ({
  Target: { title: t("zones.targetName"), sub: t("zones.targetSub") },
  Reach: { title: t("zones.reachName"), sub: t("zones.reachSub") },
  Safe: { title: t("zones.safeName"), sub: t("zones.safeSub") },
}[cat]);

const loadingLines = () => t("loading");

// ── DOM helpers ─────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

const fmt = (n) => Number(n).toLocaleString("en-IN");

const prefersReducedMotion =
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let initialStateLoaded = false;

// ── App state ───────────────────────────────────────────────────────────

const state = {
  meta: null,
  step: 0,
  gender: "male",
  brandBranchRatio: 0.5,
  goal: "undecided",
  branchPrefs: [],          // selected branch-preference values; [] means "Any"
  lastPayload: null,
  lastData: null,
  filterText: "",
  filterTypes: [],
  filterRegion: "all",
  filterState: "all",
  choices: JSON.parse(localStorage.getItem("disha_choices") || "[]"),
  // Extended data mode removed — always "basic" (2025 dataset).
  // TODO (reworkable): remove dataMode from state entirely once API no longer expects it.
  dataMode: "basic",
  view: localStorage.getItem("disha_view") || "branch", // "branch" or "college"
  expandedColleges: {}, // in-memory accordion toggle state
  collapsedSections: { Safe: false, Target: false, Reach: false },
  sortBy: "rank",
};

const TOTAL_STEPS = 5;

const branchOptions = () => state.meta?.branches || [];
const branchLabel = (value) => {
  const b = branchOptions().find((o) => o.value === value);
  return b ? b.label : value;
};

// ── View switching ──────────────────────────────────────────────────────

const VIEWS = ["welcome", "flow", "loading", "results", "error"];

function showView(name) {
  for (const v of VIEWS) {
    $(`view-${v}`).classList.toggle("is-active", v === name);
  }
  $("restart-btn").hidden = name === "welcome";
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  saveStateToURL();
}

// ── Rank inputs (live Indian-grouping format) ───────────────────────────

function parseRankInput(el) {
  const digits = el.value.replace(/[^\d]/g, "");
  if (!digits) return null;
  const n = parseInt(digits, 10);
  return n > 0 ? n : null;
}

function attachRankFormatting(el) {
  el.addEventListener("input", () => {
    const n = parseRankInput(el);
    el.value = n === null ? "" : fmt(n);
    saveStateToURL();
  });
}

// ── Guided flow ─────────────────────────────────────────────────────────

const stepButtonLabel = (index) =>
  index === TOTAL_STEPS - 1 ? t("flow.showColleges") : t("flow.continue");

function goToStep(index, { backwards = false } = {}) {
  state.step = index;
  document.querySelectorAll(".step").forEach((s) => {
    const active = Number(s.dataset.step) === index;
    s.hidden = !active;
    if (active) {
      s.classList.toggle("is-back", backwards);
      // retrigger entry animation
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
    const mains = parseRankInput($("mains-rank"));
    const adv = parseRankInput($("adv-rank"));
    const err = $("error-ranks");
    if (mains === null && adv === null) {
      err.textContent = t("validation.ranks");
      err.hidden = false;
      return false;
    }
    err.hidden = true;
    return true;
  }
  if (index === 2) {
    const err = $("error-state");
    if (!$("home-state").value) {
      err.textContent = t("validation.state");
      err.hidden = false;
      return false;
    }
    err.hidden = true;
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

// gender pills — the flow row and the live panel row both drive state.gender.
function setGender(value) {
  state.gender = value;
  syncGenderRows();
  updateGenderNote();
  saveStateToURL();
}

function syncGenderRows() {
  document
    .querySelectorAll("#gender-row .choice, #panel-gender-row .choice")
    .forEach((c) => {
      const on = c.dataset.value === state.gender;
      c.classList.toggle("is-selected", on);
      c.setAttribute("aria-checked", on ? "true" : "false");
    });
}

function bindGenderRow() {
  $("gender-row").addEventListener("click", (e) => {
    const btn = e.target.closest(".choice");
    if (!btn) return;
    setGender(btn.dataset.value);
  });
}

function updateGenderNote() {
  const note = $("gender-note");
  if (state.gender === "female") {
    note.textContent = t("gender.noteFemale");
  } else if (state.gender === "other") {
    note.textContent = t("gender.noteOther");
  } else {
    note.innerHTML = "&nbsp;";
  }
}

// familyIncome handlers removed to focus on admission probability insights.

// goal cards
function buildGoalCards() {
  const grid = $("goal-grid");
  grid.innerHTML = "";
  for (const id of GOAL_IDS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "goal-card";
    btn.dataset.goal = id;
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", state.goal === id ? "true" : "false");
    if (state.goal === id) btn.classList.add("is-selected");
    btn.innerHTML = `
      <span class="goal-card__icon" aria-hidden="true">${GOAL_ICONS[id]}</span>
      <span>
        <span class="goal-card__name">${escapeHtml(goalName(id))}</span>
        <span class="goal-card__desc">${escapeHtml(t(`goals.${id}.desc`))}</span>
      </span>`;
    btn.addEventListener("click", () => {
      state.goal = id;
      grid.querySelectorAll(".goal-card").forEach((c) => {
        const on = c === btn;
        c.classList.toggle("is-selected", on);
        c.setAttribute("aria-checked", on ? "true" : "false");
      });
      $("error-goal").hidden = true;
      // small pause so the selection registers visually, then advance
      setTimeout(() => { if (state.step === 3) advanceStep(); }, prefersReducedMotion ? 0 : 260);
      saveStateToURL();
    });
    grid.appendChild(btn);
  }
}

// branch-preference checkboxes — shared between the flow step and the live
// panel; both reflect and mutate state.branchPrefs ([] == "Any branch").
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
  grid.appendChild(makeBranchChip("", t("flow.branchAny"), anyActive));
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

// review
function categoryLabel() {
  const sel = $("seat-category");
  const opt = sel.options[sel.selectedIndex];
  if (!opt) return t("category.general");
  return opt.text;
}

function branchReviewValue() {
  if (!state.branchPrefs.length) return t("review.anyBranch");
  return state.branchPrefs.map(branchLabel).join(", ");
}

function renderReview() {
  const mains = parseRankInput($("mains-rank"));
  const adv = parseRankInput($("adv-rank"));
  const genderText = t(`gender.${state.gender}`);
  const notGiven = `<small>${escapeHtml(t("review.notGiven"))}</small>`;

  const rows = [
    { key: t("review.mains"), val: mains ? fmt(mains) : notGiven, step: 0 },
    { key: t("review.adv"), val: adv ? fmt(adv) : notGiven, step: 0 },
    { key: t("review.gender"), val: escapeHtml(genderText), step: 1 },
    { key: t("review.category"), val: escapeHtml(categoryLabel()), step: 1 },
    { key: t("review.state"), val: escapeHtml($("home-state").value || t("review.dash")), step: 2 },
    { key: t("review.branch"), val: escapeHtml(branchReviewValue()), step: 3 },
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
  $("meta-offline").hidden = true;
  $("begin-btn").disabled = true;
  try {
    const meta = await fetchMeta();
    state.meta = meta;

    if (meta.total_programs) $("program-count").textContent = fmt(meta.total_programs);

    const stateSel = $("home-state");
    stateSel.innerHTML = "";
    const ph = document.createElement("option");
    ph.value = "";
    ph.disabled = true;
    ph.selected = true;
    ph.id = "home-state-placeholder";
    ph.textContent = t("flow.statePlaceholder");
    stateSel.appendChild(ph);
    for (const s of meta.states) {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      stateSel.appendChild(opt);
    }

    // Initialise the data-source toggle based on server permissions.
    initDataModeToggle(meta);

    buildCategoryOptions();
    buildPanelControls();
    $("begin-btn").disabled = false;
  } catch {
    $("meta-offline").hidden = false;
  }
}

// ── Data-source toggle ────────────────────────────────────────────────────

/**
 * Show/hide the Data Source toggle pill depending on whether the server
 * permits it (meta.allow_toggle). When visible, clicking a button:
 *   1. Updates state.dataMode and saves it to localStorage.
 *   2. Updates aria-pressed on both buttons.
 *   3. Enables/disables the seat_category select accordingly.
 *   4. Triggers a live refresh if results are already showing.
 */
// Extended data mode toggle removed — initDataModeToggle(), setDataModeUI() deleted.
// applyDataModeToCategory() is kept but flagged as reworkable: it currently locks the
// category select to OPEN (legacy basic-mode behaviour).  Once the seat_filter TODO in
// recommender.py is resolved, this function should unlock the select unconditionally.
function initDataModeToggle(meta) {
  // No-op: toggle no longer exists.  Force mode to "basic" and unlock nothing yet.
  state.dataMode = "basic";
  const catSel = $("panel-seat-category");
  const catHint = $("panel-category-hint");
  // TODO (reworkable): call applyDataModeToCategory with the unlocked mode once
  // recommender.py seat_filter is verified to correctly filter all categories.
  applyDataModeToCategory("basic", catSel, catHint);
}

function applyDataModeToCategory(mode, catSel, catHint) {
  if (!catSel) return;
  buildCategoryOptions(catSel);
  catSel.disabled = false;
  if (catHint) catHint.hidden = true;
}

// ── Live panel (counsellor dashboard) ─────────────────────────────────────

// Build the editable controls that mirror — and drive — the student profile
// from the results page. Selects/options come from cached meta.
function buildPanelControls() {
  buildPanelGenderRow();
  buildPanelGoalSelect();
  buildPanelStateSelect();
  buildFilterStateSelect();
  buildCategoryOptions($("panel-seat-category"));
  renderBranchGrids();
}

function buildPanelGenderRow() {
  const row = $("panel-gender-row");
  if (!row) return;
  row.innerHTML = "";
  for (const g of ["male", "female", "other"]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "choice" + (state.gender === g ? " is-selected" : "");
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", state.gender === g ? "true" : "false");
    btn.dataset.value = g;
    btn.textContent = t(`gender.${g}`);
    btn.addEventListener("click", () => {
      setGender(g);
      schedulePanelUpdate();
    });
    row.appendChild(btn);
  }
}

function buildPanelGoalSelect() {
  const sel = $("panel-goal");
  if (!sel) return;
  const prev = state.goal;
  sel.innerHTML = "";
  for (const id of GOAL_IDS) {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = goalName(id);
    sel.appendChild(opt);
  }
  if (prev) sel.value = prev;
}

function buildPanelStateSelect() {
  const sel = $("panel-home-state");
  if (!sel || !state.meta) return;
  const prev = sel.value;
  sel.innerHTML = "";
  for (const s of state.meta.states) {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    sel.appendChild(opt);
  }
  if (prev) sel.value = prev;
}

function buildFilterStateSelect() {
  const sel = $("filter-state");
  if (!sel || !state.meta) return;
  const prev = sel.value || "all";
  sel.innerHTML = "";
  const optAll = document.createElement("option");
  optAll.value = "all";
  optAll.setAttribute("data-i18n", "stateFilter.all");
  optAll.textContent = t("stateFilter.all") || "All States";
  sel.appendChild(optAll);
  for (const s of state.meta.states) {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    sel.appendChild(opt);
  }
  sel.value = prev;
}

// Build (or relabel) a reservation-category dropdown from cached meta. Defaults
// to the flow's #seat-category but can target the panel's clone too.
function buildCategoryOptions(catSel) {
  catSel = catSel || $("seat-category");
  if (!catSel) return;
  const prev = catSel.value || "OPEN";
  const cats = state.meta?.categories?.length
    ? state.meta.categories
    : [{ value: "OPEN", label: "General", available: true }];
  catSel.innerHTML = "";
  for (const c of cats) {
    const opt = document.createElement("option");
    opt.value = c.value;
    const label = c.value === "OPEN"
      ? t("category.general")
      : String(c.label || c.value);

    opt.textContent = label;
    opt.disabled = false;
    catSel.appendChild(opt);
  }
  catSel.value = prev;
  if (!catSel.value) catSel.value = "OPEN";
  const note = $("category-note");
  if (note) note.textContent = t("category.note");
}

// ── Submission ──────────────────────────────────────────────────────────

let loadingTimer = null;
let requestSeq = 0;

function startLoadingLines() {
  let i = 0;
  const lines = loadingLines();
  $("loading-text").textContent = lines[0];
  loadingTimer = setInterval(() => {
    const ls = loadingLines();
    i = (i + 1) % ls.length;
    $("loading-text").textContent = ls[i];
  }, 1100);
}

function stopLoadingLines() {
  clearInterval(loadingTimer);
  loadingTimer = null;
}

function buildPayload() {
  const mains = parseRankInput($("mains-rank"));
  const adv = parseRankInput($("adv-rank"));
  const payload = {
    gender: state.gender === "female" ? "female" : "male",
    home_state: $("home-state").value,
    goal: state.goal,
    seat_category: $("seat-category").value || "OPEN",
    brand_branch_ratio: state.brandBranchRatio !== undefined ? state.brandBranchRatio : 0.5,
    max_results: 150,
    lang: getLang(),
    data_mode: "basic",  // extended mode removed; always send basic
  };
  if (mains !== null) payload.mains_rank = mains;
  if (adv !== null) payload.adv_rank = adv;
  if (state.branchPrefs.length) payload.branch_preferences = state.branchPrefs.slice();
  return payload;
}

async function submitProfile() {
  state.lastPayload = buildPayload();
  await runRequest(state.lastPayload);
}

// ── Live panel updates ────────────────────────────────────────────────────
// Editing a panel control re-runs the request in place — no view switch, no
// page reload — so the results feel like a live counsellor dashboard.

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
  const mains = parseRankInput($("mains-rank"));
  const adv = parseRankInput($("adv-rank"));
  // Keep the current results on screen if both ranks are cleared.
  if (mains === null && adv === null) {
    showPanelUpdating(false);
    return;
  }
  state.lastPayload = buildPayload();
  runLiveRequest(state.lastPayload);
}

// Like runRequest, but never leaves the results view: we refresh the cards in
// place and show a subtle "Updating…" cue in the panel instead.
async function runLiveRequest(payload) {
  const seq = ++requestSeq;
  showPanelUpdating(true);
  try {
    const data = await fetchRecommendations(payload);
    if (seq !== requestSeq) return;
    state.lastData = data;
    renderResults(data, { keepFilters: true });
  } catch (err) {
    if (seq !== requestSeq) return;
    // Soft-fail: keep the last good results rather than wiping the dashboard.
    console.warn("Live update failed:", err && err.message);
  } finally {
    if (seq === requestSeq) showPanelUpdating(false);
  }
}

// Copy the current profile (flow inputs + state) into the panel controls. Run
// when first arriving at results, not on every keystroke, so we never fight the
// control the user is editing.
function updatePriorityStateUI() {
  // 1. Update priority segmented toggle buttons active classes
  const priorityButtons = {
    "0.2": $("priority-branch"),
    "0.5": $("priority-balanced"),
    "0.8": $("priority-college")
  };
  const activeRatio = state.brandBranchRatio !== undefined ? state.brandBranchRatio : 0.5;
  Object.entries(priorityButtons).forEach(([val, btn]) => {
    if (btn) {
      const active = Math.abs(activeRatio - parseFloat(val)) < 0.15;
      btn.classList.toggle("is-active", active);
    }
  });

  // 2. Update toggle labels based on selected goal
  const branchBtnFull = document.querySelector("#priority-branch .full-label");
  const branchBtnShort = document.querySelector("#priority-branch .short-label");
  if (branchBtnFull && branchBtnShort) {
    if (state.goal && state.goal !== "undecided") {
      const currentGoalName = goalName(state.goal);
      branchBtnFull.textContent = `${t("results.priorityBranchFull")} (${currentGoalName})`;
      branchBtnShort.textContent = `${t("results.priorityBranchShort")} (${currentGoalName})`;
    } else {
      branchBtnFull.textContent = t("results.priorityBranchFull");
      branchBtnShort.textContent = t("results.priorityBranchShort");
    }
  }

  // 3. Update warning tooltip for undecided career goal
  const tooltip = $("priority-goal-tooltip");
  if (tooltip) {
    const isFavourBranchActive = Math.abs(activeRatio - 0.2) < 0.15;
    const isGoalUndecided = (state.goal === "undecided" || !state.goal);
    tooltip.hidden = !(isFavourBranchActive && isGoalUndecided);
  }
}

function syncPanelFromState() {
  if ($("panel-mains-rank")) $("panel-mains-rank").value = $("mains-rank").value;
  if ($("panel-adv-rank")) $("panel-adv-rank").value = $("adv-rank").value;
  if ($("panel-home-state")) $("panel-home-state").value = $("home-state").value;
  if ($("panel-seat-category")) {
    $("panel-seat-category").value = $("seat-category").value || "OPEN";
  }
  if ($("panel-goal") && state.goal) $("panel-goal").value = state.goal;

  updatePriorityStateUI();

  if ($("filter-region")) $("filter-region").value = state.filterRegion || "all";
  if ($("filter-state")) $("filter-state").value = state.filterState || "all";
  syncGenderRows();
  renderBranchGrids();
}

async function runRequest(payload, { keepFilters = false } = {}) {
  const seq = ++requestSeq;
  showView("loading");
  startLoadingLines();
  const minDelay = new Promise((r) => setTimeout(r, prefersReducedMotion ? 0 : 1100));

  try {
    const [data] = await Promise.all([fetchRecommendations(payload), minDelay]);
    if (seq !== requestSeq) return;
    stopLoadingLines();
    state.lastData = data;
    renderResults(data, { keepFilters });
    syncPanelFromState();
    showView("results");
  } catch (err) {
    if (seq !== requestSeq) return;
    stopLoadingLines();
    $("error-message").textContent = err.message || t("error.generic");
    showView("error");
  }
}

// ── Results rendering ───────────────────────────────────────────────────

function countUp(el, target) {
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
  if (p.mains_rank) chips.push(`${escapeHtml(t("results.profileMain"))} <strong>${fmt(p.mains_rank)}</strong>`);
  if (p.adv_rank) chips.push(`${escapeHtml(t("results.profileAdvanced"))} <strong>${fmt(p.adv_rank)}</strong>`);
  chips.push(escapeHtml(p.home_state));
  chips.push(escapeHtml(categoryLabel()));
  if (state.goal) chips.push(escapeHtml(goalName(state.goal)));
  for (const b of state.branchPrefs) chips.push(escapeHtml(branchLabel(b)));

  // Data source mode badge removed — extended mode no longer available.
  $("profile-chips").innerHTML =
    chips.map((c) => `<span class="pchip">${c}</span>`).join("");
}

function noteHeadline(byCat, total) {
  if (total === 0) return t("headlines.adjust");
  if ((byCat.Target || 0) > 0 && (byCat.Safe || 0) > 0) return t("headlines.good");
  if ((byCat.Target || 0) > 0) return t("headlines.options");
  if ((byCat.Safe || 0) > 0) return t("headlines.solid");
  return t("headlines.stretch");
}

function renderNote(data) {
  const byCat = data.counts?.by_category || {};
  const total = data.counts?.total ?? 0;

  $("note-headline").textContent = noteHeadline(byCat, total);

  const pieces = [];
  if (data.interest_guidance) pieces.push(data.interest_guidance);
  if (data.guidance) pieces.push(data.guidance);
  $("note-guidance").textContent = pieces.join(" ");

  const tips = state.goal ? goalTips(state.goal) : [];
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
}

function userRankFor(rec) {
  return rec.exam === "advanced"
    ? state.lastPayload.adv_rank
    : state.lastPayload.mains_rank;
}

// ── Rank ruler (hero) ─────────────────────────────────────────────────────
/*
  DESIGN CHOICE — THREE stacked rulers, not one.
  JEE Advanced (IIT) and JEE Main (NIT/IIIT/GFTI) ranks come from different
  exams and different candidate pools, so they sit on separate scales. IITs are
  further split into Top 5 (Bombay, Delhi, Madras, Kanpur, Kharagpur) and Rest
  so students can see where they stand in each tier. Each ruler has its own YOU
  line. The axis autoscales to fit the data, with zoom/pan controls.
  HOW TO READ IT — the axis is logarithmic (rank 1 → 10 lakh) so the crowded
  low-rank end stays legible; each dot is one program coloured Safe/Target/Reach,
  and the black "YOU" line is the student's rank: dots to its LEFT closed at a
  better (lower) rank than them, dots to its RIGHT closed later.
*/

const RANK_AXIS_MAX = 1000000;
const LOG_AXIS_MAX = Math.log10(RANK_AXIS_MAX); // 6

// pos(rank) → percentage along the axis on a log10 scale (a linear scale is
// useless when ranks span 1 … 10⁶). Clamped so edge dots stay inside the track.
function rankPos(rank) {
  const r = Math.min(Math.max(Number(rank) || 1, 1), RANK_AXIS_MAX);
  return Math.min(Math.max((Math.log10(r) / LOG_AXIS_MAX) * 100, 0.5), 99.5);
}

// Scoped position within a given log range [logMin, logMax]
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
  { rank: 500000, label: "5L" },
  { rank: 1000000, label: "10L" },
];

// Select a reasonable subset of ticks for a given log range
function ticksForRange(logMin, logMax) {
  const visible = ALL_TICKS.filter(t => {
    const logR = Math.log10(t.rank || 1);
    return logR >= logMin - 0.05 && logR <= logMax + 0.05;
  });
  // If too many, pick every other
  if (visible.length > 8) return visible.filter((_, i) => i % 2 === 0);
  return visible;
}

const RULER_TICKS = [
  { rank: 10, label: "10" },
  { rank: 100, label: "100" },
  { rank: 1000, label: "1K" },
  { rank: 10000, label: "10K" },
  { rank: 100000, label: "1L" },
  { rank: 1000000, label: "10L" },
];

const RULER_GROUPS = [
  { id: "iit", exam: "advanced", titleKey: "ruler.iitTitle", viaKey: "ruler.iitVia", rankKey: "adv_rank" },
  { id: "mains", exam: "mains", titleKey: "ruler.nitTitle", viaKey: "ruler.nitVia", rankKey: "mains_rank" },
];

const RULER_LANES = 4; // vertical jitter lanes to de-clutter dense clusters

// Per-group zoom state: { logMin, logMax, defaultLogMin, defaultLogMax }
const rulerZoomState = {};

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

function rulerGroupHtml(group, recs) {
  let items = recs.filter((r) => r.exam === group.exam);
  // Apply optional sub-filter (e.g. Top 5 IITs vs Rest)
  if (group.filter) items = items.filter(group.filter);
  if (!items.length) return "";

  const title = t(group.titleKey);
  const via = t(group.viaKey);
  const youRank = state.lastPayload?.[group.rankKey];
  // sort by closing rank so adjacent (visually overlapping) dots land in
  // different jitter lanes, spreading dense clusters vertically
  const sorted = items.slice().sort((a, b) => a.closing_rank - b.closing_rank);

  // Compute autoscaled range
  const autoRange = computeAutoRange(items, youRank);
  const gid = group.id;
  if (!rulerZoomState[gid]) {
    // First render: use autoscale as both current and default range
    rulerZoomState[gid] = {
      logMin: autoRange.logMin,
      logMax: autoRange.logMax,
      defaultLogMin: autoRange.logMin,
      defaultLogMax: autoRange.logMax,
    };
  } else {
    // Re-render (e.g. live update): keep zoomed position, update defaults
    rulerZoomState[gid].defaultLogMin = autoRange.logMin;
    rulerZoomState[gid].defaultLogMax = autoRange.logMax;
  }
  rulerZoomState[gid].dotLogs = sorted.map(r => Math.log10(r.closing_rank));
  const { logMin, logMax } = rulerZoomState[gid];

  const lanes = [];
  const numLanes = 8;
  for (let l = 0; l < numLanes; l++) lanes[l] = -100;

  const dots = sorted
    .map((r) => {
      const cat = r.category.toLowerCase();
      const absPos = Math.log10(r.closing_rank);
      let bestLane = 0;
      let maxDist = -1;
      for (let l = 0; l < numLanes; l++) {
        const dist = absPos - lanes[l];
        if (dist > maxDist) {
          maxDist = dist;
          bestLane = l;
        }
      }
      lanes[bestLane] = absPos;
      const topPct = 10 + (bestLane / (numLanes - 1)) * 80;
      const leftPct = rankPosScoped(r.closing_rank, logMin, logMax);
      return `<span class="ruler__dot ruler__dot--${cat}" style="left:${leftPct.toFixed(2)}%; top:${topPct.toFixed(2)}%" data-inst="${escapeHtml(r.institute)}" data-branch="${escapeHtml(r.branch)}" data-rank="${r.closing_rank}" data-cat="${cat}"></span>`;
    })
    .join("");

  const visibleTicks = ticksForRange(logMin, logMax);

  const grid = visibleTicks.map(
    (tk) => `<span class="ruler__grid" style="left:${rankPosScoped(tk.rank, logMin, logMax).toFixed(2)}%"></span>`
  ).join("");

  const scale = visibleTicks.map(
    (tk) => `<span class="ruler__tick" style="left:${rankPosScoped(tk.rank, logMin, logMax).toFixed(2)}%">${tk.label}</span>`
  ).join("");

  const you = youRank
    ? `<div class="ruler__you" style="left:${rankPosScoped(youRank, logMin, logMax).toFixed(2)}%" title="${escapeHtml(t("ruler.yourRank", { rank: fmt(youRank) }))}"><span class="ruler__you-flag">${escapeHtml(t("ruler.you"))}</span></div>`
    : "";

  const headRight = youRank
    ? `<span class="ruler__you-rank">${escapeHtml(t("ruler.you"))} · ${fmt(youRank)}</span>`
    : `<span class="ruler__count">${items.length} ${escapeHtml(t("ruler.options"))}</span>`;

  const aria = `${title} ${via}: ${items.length}`;

  return `
    <div class="ruler__group" role="img" aria-label="${escapeHtml(aria)}" data-ruler-id="${gid}">
      <div class="ruler__head">
        <span class="ruler__title">${escapeHtml(title)} <span class="ruler__via">${escapeHtml(via)}</span></span>
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

// Re-render a single ruler group in-place after zoom/pan
function rerenderRulerGroup(rulerId) {
  const data = state.lastData;
  if (!data) return;
  const recs = data.recommendations || [];
  const group = RULER_GROUPS.find(g => g.id === rulerId);
  if (!group) return;
  const groupEl = document.querySelector(`.ruler__group[data-ruler-id="${rulerId}"]`);
  if (!groupEl) return;
  const newHtml = rulerGroupHtml(group, recs);
  if (!newHtml) return;
  const temp = document.createElement("div");
  temp.innerHTML = newHtml;
  const newGroup = temp.firstElementChild;
  groupEl.replaceWith(newGroup);
  // Re-wire zoom/pan on the fresh DOM nodes
  bindRulerZoom();
}

// ── Zoom / pan helpers ──────────────────────────────────────────────────
const MIN_LOG_SPAN = 0.4; // prevent zooming into a point

function applyClampedRange(zs, newMin, newMax, action) {
  const minAllowed = 0;
  const maxAllowed = LOG_AXIS_MAX;
  const maxSpan = (zs.defaultLogMax || LOG_AXIS_MAX) - (zs.defaultLogMin || 0);

  let currentSpan = newMax - newMin;
  if (currentSpan > maxSpan) {
    const center = (newMin + newMax) / 2;
    newMin = center - maxSpan / 2;
    newMax = center + maxSpan / 2;
  }

  if (newMin < minAllowed) { newMax += (minAllowed - newMin); newMin = minAllowed; }
  if (newMax > maxAllowed) { newMin -= (newMax - maxAllowed); newMax = maxAllowed; }
  
  newMin = Math.max(minAllowed, newMin);
  newMax = Math.min(maxAllowed, newMax);
  
  if (newMax - newMin < 0.001) {
    newMax = newMin + 0.001;
  }

  let hasDot = false;
  if (zs.dotLogs && zs.dotLogs.length > 0) {
    for (let i = 0; i < zs.dotLogs.length; i++) {
      if (zs.dotLogs[i] >= newMin && zs.dotLogs[i] <= newMax) {
        hasDot = true;
        break;
      }
    }
  } else {
    hasDot = true;
  }

  if (!hasDot && zs.dotLogs && zs.dotLogs.length > 0) {
    const span = newMax - newMin;
    if (action === "pan") {
      if (zs.dotLogs[zs.dotLogs.length - 1] < newMin) {
        newMin = zs.dotLogs[zs.dotLogs.length - 1];
        newMax = newMin + span;
      } else if (zs.dotLogs[0] > newMax) {
        newMax = zs.dotLogs[0];
        newMin = newMax - span;
      }
    } else if (action === "zoomIn") {
      const center = (newMin + newMax) / 2;
      let closestDist = Infinity;
      for (let i = 0; i < zs.dotLogs.length; i++) {
        const dist = Math.abs(zs.dotLogs[i] - center);
        if (dist < closestDist) {
          closestDist = dist;
        }
      }
      newMin = center - closestDist - 0.001;
      newMax = center + closestDist + 0.001;
    }
    
    if (newMin < minAllowed) { newMax += (minAllowed - newMin); newMin = minAllowed; }
    if (newMax > maxAllowed) { newMin -= (newMax - maxAllowed); newMax = maxAllowed; }
    newMin = Math.max(minAllowed, newMin);
    newMax = Math.min(maxAllowed, newMax);
    
    if (newMax - newMin < 0.001) {
      newMax = newMin + 0.001;
    }
  }

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

// Wire zoom buttons + wheel + drag on every .ruler__group currently in the DOM.
// Called after renderRuler and after each rerenderRulerGroup.
function bindRulerZoom() {
  // Zoom buttons (direct binding, not delegation)
  document.querySelectorAll(".ruler__zoom-btn").forEach(btn => {
    // Avoid double-binding
    if (btn._zoomBound) return;
    btn._zoomBound = true;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const action = btn.dataset.action;
      const rulerId = btn.dataset.rulerId;
      applyZoom(rulerId, action);
    });
  });

  // Wheel zoom on each track
  document.querySelectorAll(".ruler__track").forEach(track => {
    if (track._wheelBound) return;
    track._wheelBound = true;
    track.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rulerId = track.dataset.rulerId;
      if (!rulerId) return;
      // Scroll up / pinch out = zoom in, scroll down = zoom out
      const action = e.deltaY < 0 ? "in" : "out";
      applyZoom(rulerId, action);
    }, { passive: false });
  });

  // Keyboard zoom/pan on each track
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

  // Drag-to-pan on each track
  document.querySelectorAll(".ruler__track").forEach(track => {
    if (track._dragBound) return;
    track._dragBound = true;
    let dragging = false;
    let startX = 0;
    let startLogMin = 0;
    let startLogMax = 0;

    track.addEventListener("pointerdown", (e) => {
      // Ignore if clicking a dot
      if (e.target.closest(".ruler__dot") || e.target.closest(".ruler__you")) return;
      const rulerId = track.dataset.rulerId;
      const zs = rulerZoomState[rulerId];
      if (!zs) return;
      dragging = true;
      startX = e.clientX;
      startLogMin = zs.logMin;
      startLogMax = zs.logMax;
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

    const stopDrag = () => {
      dragging = false;
      track.style.cursor = "";
    };
    track.addEventListener("pointerup", stopDrag);
    track.addEventListener("pointercancel", stopDrag);
  });
}

// Built once per result render (not on filter changes) to keep typing snappy.
function renderRuler(data, keepZoom = false) {
  const el = $("ruler");
  const recs = data?.recommendations || [];
  if (!keepZoom) {
    // Reset zoom state for fresh renders
    for (const key of Object.keys(rulerZoomState)) delete rulerZoomState[key];
  }
  const groups = RULER_GROUPS.map((g) => rulerGroupHtml(g, recs)).filter(Boolean).join("");

  if (!groups) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }

  el.innerHTML = `
    <div class="ruler__intro">
      <p class="eyebrow">${escapeHtml(t("ruler.introEyebrow"))}</p>
      <p class="ruler__lede">${t("ruler.lede")}</p>
    </div>
    ${groups}
    <div class="ruler__tip" id="ruler-tip" aria-hidden="true"></div>`;
  el.hidden = false;
  // Wire zoom/pan on the freshly rendered DOM
  bindRulerZoom();
}

// Cheap tooltip via event delegation: hover (pointer) or tap (touch) a dot.
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
      `<em>${escapeHtml(t("ruler.closes"))} ${fmt(Number(dot.dataset.rank))}</em>`;
    tip.dataset.cat = dot.dataset.cat;
    tip.style.left = `${dr.left - cr.left + dr.width / 2}px`;
    tip.style.top = `${dr.top - cr.top}px`;
    tip.classList.add("is-on");
  };

  const hideTip = () => {
    const tip = $("ruler-tip");
    if (tip) tip.classList.remove("is-on");
  };

  el.addEventListener("pointerover", (e) => {
    const dot = e.target.closest(".ruler__dot");
    if (dot) showTip(dot);
  });
  el.addEventListener("pointerout", (e) => {
    if (e.target.closest(".ruler__dot")) hideTip();
  });
  el.addEventListener("click", (e) => {
    const dot = e.target.closest(".ruler__dot");
    if (dot) showTip(dot);
    else if (!e.target.closest(".ruler__zoom-btn")) hideTip();
  });
}

function rankBarHtml(rec) {
  const open = rec.opening_rank;
  const close = rec.closing_rank;
  const rank = userRankFor(rec);
  const span = Math.max(close - open, 1);
  const trackLo = open - span * 0.45;
  const trackHi = close + span * 0.45;
  const pos = (v) => ((v - trackLo) / (trackHi - trackLo)) * 100;

  const winLeft = pos(open);
  const winRight = pos(close);
  const youPos = Math.min(Math.max(pos(rank), 3), 97);

  let verdict;
  if (rec.category === "Safe") {
    verdict = t("rankbar.safe", { rank: fmt(rank) });
  } else if (rec.category === "Target") {
    const through = Math.round(((rank - open) / span) * 100);
    verdict =
      through <= 55
        ? t("rankbar.targetComfort", { rank: fmt(rank) })
        : t("rankbar.targetEdge", { rank: fmt(rank) });
  } else {
    const past = Math.max(1, Math.round(((rank - close) / close) * 100));
    verdict = t("rankbar.reach", { rank: fmt(rank), past });
  }

  return `
    <div class="rankbar">
      <div class="rankbar__track">
        <div class="rankbar__window" style="left:${winLeft.toFixed(1)}%;right:${(100 - winRight).toFixed(1)}%"></div>
        <div class="rankbar__you" style="left:${youPos.toFixed(1)}%" title="${escapeHtml(t("ruler.yourRank", { rank: fmt(rank) }))}"></div>
      </div>
      <div class="rankbar__labels">
        <span>${escapeHtml(t("rankbar.opens"))} <strong>${fmt(open)}</strong></span>
        <span>${escapeHtml(t("rankbar.closes"))} <strong>${fmt(close)}</strong></span>
      </div>
      <p class="rankbar__verdict">${escapeHtml(verdict)}</p>
    </div>`;
}

// Volatility tag -> localized label, hint (interpolating flag_round), and CSS class mapping.
function confidenceMeta(band, flagRound) {
  let styleClass = "medium";
  let labelKey = "mediumLabel";
  let hintKey = "mediumHint";

  if (band === "highly_stable") {
    styleClass = "high";
    labelKey = "highly_stableLabel";
    hintKey = "highly_stableHint";
  } else if (band === "stable_drift") {
    styleClass = "medium";
    labelKey = "stable_driftLabel";
    hintKey = "stable_driftHint";
  } else if (band === "volatile_vacancy") {
    styleClass = "fragile";
    labelKey = "volatile_vacancyLabel";
    hintKey = "volatile_vacancyHint";
  } else if (band === "volatile_erratic") {
    styleClass = "fragile";
    labelKey = "volatile_erraticLabel";
    hintKey = "volatile_erraticHint";
  } else {
    // Fallback for any legacy bands
    const b = ["high", "medium", "fragile"].includes(band) ? band : "medium";
    styleClass = b;
    labelKey = `${b}Label`;
    hintKey = `${b}Hint`;
  }

  return {
    styleClass,
    label: t(`confidence.${labelKey}`),
    hint: t(`confidence.${hintKey}`, { r: flagRound || "" })
  };
}

function confidenceChipHtml(rec) {
  const meta = confidenceMeta(rec.confidence, rec.flag_round);
  return `<span class="conf-chip conf-chip--${escapeHtml(meta.styleClass)}" title="${escapeHtml(meta.hint)}">${escapeHtml(meta.label)}</span>`;
}

function advantageBadgesHtml(rec) {
  const badges = [];
  if (rec.home_state_advantage) {
    badges.push(
      `<span class="adv-badge adv-badge--home" title="${escapeHtml(t("card.homeBadgeTitle"))}">
         <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>
         ${escapeHtml(t("card.homeBadge", { n: fmt(rec.home_state_advantage) }))}
       </span>`
    );
  }
  if (rec.female_seat_advantage) {
    badges.push(
      `<span class="adv-badge adv-badge--female" title="${escapeHtml(t("card.femaleBadgeTitle"))}">
         <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="5"/><path d="M12 13v8M9 18h6"/></svg>
         ${escapeHtml(t("card.femaleBadge", { n: fmt(rec.female_seat_advantage) }))}
       </span>`
    );
  }
  return badges.length ? `<div class="ccard__badges">${badges.join("")}</div>` : "";
}

function probabilityBadgeHtml(rec) {
  if (rec.admission_probability === null || rec.admission_probability === undefined) return "";
  const prob = rec.admission_probability;
  let probClass = "low";
  if (prob >= 75) {
    probClass = "high";
  } else if (prob >= 35) {
    probClass = "medium";
  }
  const text = `${Math.round(prob)}% ${t("card.chance")}`;
  const title = t("card.probTitle", { prob: Math.round(prob) });
  return `<span class="tag tag--prob tag--prob-${probClass}" title="${escapeHtml(title)}">${escapeHtml(text)}</span>`;
}

function historyTableHtml(rec) {
  if (!rec.history || Object.keys(rec.history).length <= 1) return "";
  const sortedYears = Object.keys(rec.history).sort((a, b) => Number(a) - Number(b));

  let html = `<div class="history-timeline">`;
  for (const year of sortedYears) {
    const isCurrent = year === "2025";
    const rankVal = rec.history[year];
    html += `
      <div class="history-timeline__item ${isCurrent ? "is-current" : ""}">
        <span class="history-timeline__year">${year}</span>
        <span class="history-timeline__rank">${fmt(rankVal)}</span>
      </div>`;
  }
  html += `</div>`;
  return html;
}

function cardHtml(rec, index) {
  const cat = rec.category.toLowerCase();
  const typeClass = `tag--${rec.institute_type.toLowerCase()}`;
  const delay = prefersReducedMotion ? 0 : Math.min(index * 45, 420);
  const star = rec.matched_interest
    ? `<span class="ccard__star" title="${escapeHtml(t("card.fitsGoalTitle"))}">
         <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8L12 2z"/></svg>
         ${escapeHtml(t("card.fitsGoal"))}</span>`
    : "";

  const degreeNote = /dual/i.test(rec.degree) ? t("card.dualDegree") : "";
  const poolNote = rec.gender_pool === "female" ? t("card.femaleSeat") : "";
  const foot = [
    quotaLabel(rec.quota),
    rec.exam === "advanced" ? t("card.viaAdvanced") : t("card.viaMains"),
    degreeNote,
    poolNote,
  ].filter(Boolean);

  const reason = rec.reason
    ? `<p class="ccard__reason">${escapeHtml(rec.reason)}</p>`
    : "";

  const isBookmarked = state.choices && state.choices.some(c => c.institute === rec.institute && c.branch === rec.branch);
  const bookmarkHtml = `
    <button type="button" class="ccard__bookmark ${isBookmarked ? "is-selected" : ""}"
            data-institute="${escapeHtml(rec.institute)}"
            data-branch="${escapeHtml(rec.branch)}"
            onclick="toggleBookmark(event, ${index}, '${escapeHtml(rec.institute)}', '${escapeHtml(rec.branch)}')"
            aria-label="Add to preference list">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="bookmark-icon">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
      </svg>
    </button>`;

  // Future-proofing: Render fees only if returned by the API
  const waiverBadge = (rec.fee_waiver_applied && rec.fee_note)
    ? `<span class="tag tag--fee-waiver" title="${escapeHtml(rec.fee_note)}">Waiver</span>`
    : "";
  const feeText = (rec.estimated_fees !== undefined && rec.estimated_fees > 0)
    ? `<span class="tag tag--fee">₹${(rec.estimated_fees / 1000).toFixed(0)}k/yr</span>`
    : "";

  // Only show history if we have more than 1 year of data.
  const hasHistory = rec.history && Object.keys(rec.history).length > 1;

  return `
    <article class="ccard ccard--${cat}" style="animation-delay:${delay}ms">
      ${bookmarkHtml}
      <div class="ccard__meta">
        <span class="tag ${typeClass}">${escapeHtml(rec.institute_type)}</span>
        <span class="tag">${escapeHtml(rec.institute_state)}</span>
        ${feeText}
        ${waiverBadge}
        ${probabilityBadgeHtml(rec)}
        ${confidenceChipHtml(rec)}
        ${star}
      </div>
      <h3 class="ccard__institute">${escapeHtml(rec.institute)}</h3>
      <p class="ccard__branch">${escapeHtml(rec.branch)}</p>
      ${rankBarHtml(rec)}
      ${advantageBadgesHtml(rec)}
      ${reason}

      ${hasHistory ? `
      <button type="button" class="ccard__history-btn" onclick="toggleHistory(event, this)">
        <span>${escapeHtml(t("card.historyBtn"))}</span>
        <svg class="chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <div class="ccard__history-collapse" hidden>
        <div class="ccard__history-body">
          ${historyTableHtml(rec)}
        </div>
      </div>
      ` : ""}

      <div class="ccard__foot">${foot.map((f) => `<span>${escapeHtml(f)}</span>`).join("")}</div>
    </article>`;
}

// ── Choice List bookmarking, sorting and exports ──────────────────────────

window.toggleHistory = function (event, btn) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const card = btn.closest(".ccard");
  const collapse = card.querySelector(".ccard__history-collapse");
  const isHidden = collapse.hidden;

  collapse.hidden = !isHidden;
  btn.classList.toggle("is-expanded", isHidden);

  const btnText = btn.querySelector("span");
  if (btnText) {
    btnText.textContent = isHidden ? t("card.historyBtnClose") : t("card.historyBtn");
  }
};

window.toggleBookmark = function (event, index, institute, branch) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const idx = state.choices.findIndex(c => c.institute === institute && c.branch === branch);
  if (idx > -1) {
    state.choices.splice(idx, 1);
  } else {
    const recommendations = state.lastData?.recommendations || [];
    const rec = recommendations.find(r => r.institute === institute && r.branch === branch);
    if (!rec) return;
    state.choices.push({
      institute: rec.institute,
      institute_type: rec.institute_type,
      branch: rec.branch,
      branch_full: rec.branch_full,
      degree: rec.degree,
      // Future-proofing: Preserve fees parameters if returned by API
      estimated_fees: rec.estimated_fees,
      fee_waiver_applied: rec.fee_waiver_applied,
      fee_note: rec.fee_note,
      quota: rec.quota,
      opening_rank: rec.opening_rank,
      closing_rank: rec.closing_rank,
      category: rec.category,
      fit_label: rec.fit_label
    });
  }
  localStorage.setItem("disha_choices", JSON.stringify(state.choices));
  updateChoiceUI();
};

window.moveChoice = function (index, direction) {
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= state.choices.length) return;
  const temp = state.choices[index];
  state.choices[index] = state.choices[targetIndex];
  state.choices[targetIndex] = temp;
  localStorage.setItem("disha_choices", JSON.stringify(state.choices));
  updateChoiceUI();
};

function updateChoiceUI() {
  const trigger = $("choice-list-trigger");
  const count = $("choice-count");
  const clearBtn = $("choice-clear-all");

  if (count) count.textContent = state.choices.length;
  if (clearBtn) {
    clearBtn.style.display = state.choices.length > 0 ? "inline-block" : "none";
  }

  const inResultsView = $("view-results").classList.contains("is-active");
  if (trigger) {
    trigger.style.display = (inResultsView && state.choices.length > 0) ? "flex" : "none";
  }

  // Update card bookmark buttons
  document.querySelectorAll(".ccard__bookmark").forEach(btn => {
    const inst = btn.dataset.institute;
    const br = btn.dataset.branch;
    const bookmarked = state.choices.some(c => c.institute === inst && c.branch === br);
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
      <div class="choice-drawer__handle" aria-label="Drag to reorder" style="display: none;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>
      </div>
      <div class="choice-drawer__item-info">
        <span class="choice-drawer__item-rank">#${idx + 1}</span>
        <div>
          <strong class="choice-drawer__item-inst">${escapeHtml(c.institute || "")}</strong>
          <span class="choice-drawer__item-branch">${escapeHtml(c.branch || "")}</span>
        </div>
      </div>
      <button type="button" class="choice-drawer__item-remove" onclick="toggleBookmark(event, null, '${escapeHtml(c.institute || "")}', '${escapeHtml(c.branch || "")}')">&times;</button>
    `;

    // Drag and Drop Event Listeners
    li.addEventListener("dragstart", (e) => {
      draggedIndex = idx;
      li.classList.add("is-dragging");
      e.dataTransfer.effectAllowed = "move";
    });

    li.addEventListener("dragend", () => {
      li.classList.remove("is-dragging");
      draggedIndex = null;
    });

    li.addEventListener("dragover", (e) => {
      e.preventDefault();
      li.classList.add("is-dragover");
    });

    li.addEventListener("dragleave", () => {
      li.classList.remove("is-dragover");
    });

    li.addEventListener("drop", (e) => {
      e.preventDefault();
      li.classList.remove("is-dragover");
      if (draggedIndex === null || draggedIndex === idx) return;

      const moved = state.choices.splice(draggedIndex, 1)[0];
      state.choices.splice(idx, 0, moved);
      localStorage.setItem("disha_choices", JSON.stringify(state.choices));
      updateChoiceUI();
    });

    list.appendChild(li);
  });
}

window.clearChoices = function () {
  if (state.choices.length === 0) return;
  if (confirm("Are you sure you want to clear your entire preference list?")) {
    state.choices = [];
    localStorage.setItem("disha_choices", JSON.stringify(state.choices));
    updateChoiceUI();
    $("choice-drawer").hidden = true;
  }
};

function exportChoicesCSV() {
  if (state.choices.length === 0) return;
  const hasFees = state.choices.some(c => c.estimated_fees !== undefined);
  let headers = ["Preference Number", "Institute", "Branch", "Degree"];
  if (hasFees) {
    headers.push("Estimated Fees", "Fee Notes");
  }
  headers.push("Category");
  let csv = headers.join(",") + "\n";
  state.choices.forEach((c, idx) => {
    const row = [
      idx + 1,
      `"${(c.institute || "").replace(/"/g, '""')}"`,
      `"${(c.branch || "").replace(/"/g, '""')}"`,
      `"${(c.degree || "").replace(/"/g, '""')}"`
    ];
    if (hasFees) {
      const feeStr = c.estimated_fees > 0 ? `₹${(c.estimated_fees / 1000).toFixed(0)}k/year` : "Free / Fully Waived";
      row.push(`"${feeStr}"`, `"${(c.fee_note || "").replace(/"/g, '""')}"`);
    }
    row.push(`"${c.category || ""}"`);
    csv += row.join(",") + "\n";
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", "my_disha_choices.csv");
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function printChoices() {
  if (state.choices.length === 0) return;
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    alert("Please allow popups to print your preference list.");
    return;
  }

  const hasFees = state.choices.some(c => c.estimated_fees !== undefined);
  let rowsHtml = state.choices.map((c, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td><strong>${escapeHtml(c.institute || "")}</strong></td>
      <td>${escapeHtml(c.branch || "")}</td>
      <td>${escapeHtml(c.degree || "")}</td>
      ${hasFees ? `<td>${c.estimated_fees > 0 ? `₹${(c.estimated_fees / 1000).toFixed(0)}k/yr` : "Fully Waived"}</td>` : ""}
    </tr>
  `).join("");

  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>My Disha Preference List</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #333; padding: 40px; }
        h1 { margin-bottom: 8px; color: #111; }
        p { color: #666; font-size: 14px; margin-bottom: 24px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #e0e0e0; padding: 12px 16px; text-align: left; }
        th { background-color: #f7f7f7; font-weight: 600; }
        tr:nth-child(even) { background-color: #fafafa; }
        @media print {
          body { padding: 0; }
          button { display: none; }
        }
      </style>
    </head>
    <body>
      <h1>UTMT Disha - My Preference List</h1>
      <p>Customized JEE branch and college choices generated on ${new Date().toLocaleDateString()}.</p>
      <table>
        <thead>
          <tr>
            <th style="width: 60px;">Pref #</th>
            <th>Institute</th>
            <th>Branch</th>
            <th>Degree</th>
            ${hasFees ? `<th>Est. Fees</th>` : ""}
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
      <script>
        window.onload = function() {
          window.print();
          setTimeout(function() { window.close(); }, 500);
        };
      </script>
    </body>
    </html>
  `);
  printWindow.document.close();
}

function recPassesFilters(rec) {
  if (state.filterTypes && state.filterTypes.length > 0) {
    let match = false;
    for (const type of state.filterTypes) {
      if (type === "IIT_TOP5" && rec.institute_type === "IIT" && rec.is_top_iit) {
        match = true;
        break;
      } else if (type === "IIT_REST" && rec.institute_type === "IIT" && !rec.is_top_iit) {
        match = true;
        break;
      } else if (rec.institute_type === type) {
        match = true;
        break;
      }
    }
    if (!match) return false;
  }
  if (state.filterRegion && state.filterRegion !== "all") {
    if (state.filterRegion === "metro" && !rec.is_metro) return false;
    if (state.filterRegion !== "metro" && rec.region !== state.filterRegion) return false;
  }
  if (state.filterState && state.filterState !== "all" && rec.institute_state !== state.filterState) return false;
  if (!state.filterText) return true;
  const q = state.filterText;
  return (
    rec.institute.toLowerCase().includes(q) ||
    rec.branch.toLowerCase().includes(q) ||
    rec.branch_full.toLowerCase().includes(q) ||
    rec.institute_state.toLowerCase().includes(q)
  );
}

function syncViewToggleUI() {
  const btnBranch = $("view-by-branch");
  const btnCollege = $("view-by-college");
  if (btnBranch && btnCollege) {
    btnBranch.classList.toggle("is-active", state.view === "branch");
    btnCollege.classList.toggle("is-active", state.view === "college");
  }
}

function getCollegeLocation(rec) {
  const parts = rec.institute.split(",");
  if (parts.length > 1) {
    return parts[1].trim();
  }
  if (rec.institute.startsWith("Indian Institute of Technology")) {
    return rec.institute.replace("Indian Institute of Technology", "").trim();
  }
  if (rec.institute.startsWith("Indian Institute of Information Technology")) {
    return rec.institute.replace("Indian Institute of Information Technology", "").trim();
  }
  return rec.institute_state;
}

function getCollegeDomId(instName) {
  return "college-" + instName.toLowerCase().replace(/[^a-z0-9]/g, "-");
}

window.toggleCollegeCard = function(event, instName) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
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
  const star = r.matched_interest
    ? `<span class="ccard__star" title="${escapeHtml(t("card.fitsGoalTitle"))}">
         <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8L12 2z"/></svg>
         ${escapeHtml(t("card.fitsGoal"))}</span>`
    : "";

  const degreeNote = /dual/i.test(r.degree) ? t("card.dualDegree") : "";
  const poolNote = r.gender_pool === "female" ? t("card.femaleSeat") : "";
  const foot = [
    quotaLabel(r.quota),
    degreeNote,
    poolNote,
  ].filter(Boolean);

  const reason = r.reason
    ? `<p class="ccard__reason">${escapeHtml(r.reason)}</p>`
    : "";

  const isBookmarked = state.choices && state.choices.some(c => c.institute === r.institute && c.branch === r.branch);
  const bookmarkHtml = `
    <button type="button" class="ccard__bookmark ${isBookmarked ? "is-selected" : ""}"
            data-institute="${escapeHtml(r.institute)}"
            data-branch="${escapeHtml(r.branch)}"
            onclick="toggleBookmark(event, ${index}, '${escapeHtml(r.institute)}', '${escapeHtml(r.branch)}')"
            aria-label="Add to preference list">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="bookmark-icon">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
      </svg>
    </button>`;

  const waiverBadge = (r.fee_waiver_applied && r.fee_note)
    ? `<span class="tag tag--fee-waiver" title="${escapeHtml(r.fee_note)}">Waiver</span>`
    : "";
  const feeText = (r.estimated_fees !== undefined && r.estimated_fees > 0)
    ? `<span class="tag tag--fee">₹${(r.estimated_fees / 1000).toFixed(0)}k/yr</span>`
    : "";

  const hasHistory = r.history && Object.keys(r.history).length > 1;

  return `
    <article class="ccard ccard--${cat} ccard--subbranch" style="animation-delay:${delay}ms; margin-top: 10px; box-shadow: none; border-color: var(--line);">
      ${bookmarkHtml}
      <div class="ccard__meta">
        ${feeText}
        ${waiverBadge}
        ${probabilityBadgeHtml(r)}
        ${confidenceChipHtml(r)}
        ${star}
      </div>
      <p class="ccard__branch" style="font-size: 0.95rem; font-weight: 600; margin-top: 4px;">${escapeHtml(r.branch)}</p>
      ${rankBarHtml(r)}
      ${advantageBadgesHtml(r)}
      ${reason}

      ${hasHistory ? `
      <button type="button" class="ccard__history-btn" onclick="toggleHistory(event, this)">
        <span>${escapeHtml(t("card.historyBtn"))}</span>
        <svg class="chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <div class="ccard__history-collapse" hidden>
        <div class="ccard__history-body">
          ${historyTableHtml(r)}
        </div>
      </div>
      ` : ""}

      <div class="ccard__foot">${foot.map((f) => `<span>${escapeHtml(f)}</span>`).join("")}</div>
    </article>`;
}

function collegeCardHtml(group, catName, index) {
  const firstRec = group.branches[0];
  const instName = group.institute;
  const instType = firstRec.institute_type;
  const typeClass = `tag--${instType.toLowerCase()}`;
  const city = getCollegeLocation(firstRec);
  const branchCount = group.branches.length;
  const isExpanded = !!state.expandedColleges[instName];
  const catClass = catName.toLowerCase();
  
  const delay = prefersReducedMotion ? 0 : Math.min(index * 45, 420);
  const viaExamText = firstRec.exam === "advanced" ? t("card.viaAdvanced") : t("card.viaMains");
  const domId = getCollegeDomId(instName);

  const branchRowsHtml = group.branches.map((r, bIdx) => {
    return branchRowCardHtml(r, index * 100 + bIdx);
  }).join("");

  return `
    <article class="ccard ccard--${catClass} ccard--college" style="animation-delay:${delay}ms">
      <div class="ccard__college-header ${isExpanded ? "is-expanded" : ""}" onclick="toggleCollegeCard(event, '${escapeHtml(instName)}')">
        <div class="ccard__meta" style="width: 100%;">
          <span class="tag ${typeClass}">${escapeHtml(instType)}</span>
          <span class="tag">${escapeHtml(firstRec.institute_state)}</span>
          <span class="tag" style="opacity: 0.85; border-style: dashed;">${escapeHtml(viaExamText)}</span>
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

function renderSections() {
  const data = state.lastData;
  const recs = data?.recommendations || [];
  const container = $("result-sections");
  container.innerHTML = "";

  const blurbs = {};
  for (const cg of data?.category_guidance || []) blurbs[cg.category] = cg.blurb;

  let anyShown = false;

  for (const catName of SECTION_ORDER) {
    const all = recs.filter((r) => r.category === catName);
    if (all.length === 0) continue;
    const visible = all.filter(recPassesFilters);
    if (visible.length === 0) continue;
    anyShown = true;

    const meta = sectionMeta(catName);
    const section = document.createElement("section");
    section.className = "rsection";
    section.id = `section-${catName.toLowerCase()}`;

    const sortedVisible = [...visible];
    if (state.sortBy === "probability") {
      sortedVisible.sort((a, b) => {
        const valA = a.admission_probability !== null && a.admission_probability !== undefined ? a.admission_probability : 0;
        const valB = b.admission_probability !== null && b.admission_probability !== undefined ? b.admission_probability : 0;
        return valB - valA;
      });
    } else if (state.sortBy === "rank") {
      sortedVisible.sort((a, b) => {
        const valA = a.closing_rank !== null && a.closing_rank !== undefined ? a.closing_rank : Infinity;
        const valB = b.closing_rank !== null && b.closing_rank !== undefined ? b.closing_rank : Infinity;
        return valA - valB;
      });
    } else if (state.sortBy === "college") {
      sortedVisible.sort((a, b) => {
        const instA = a.institute || "";
        const instB = b.institute || "";
        return instA.localeCompare(instB);
      });
    }

    let contentHtml = "";
    if (state.view === "college") {
      const grouped = [];
      visible.forEach((r) => {
        let group = grouped.find((g) => g.institute === r.institute);
        if (!group) {
          group = { institute: r.institute, branches: [] };
          grouped.push(group);
        }
        group.branches.push(r);
      });

      if (state.sortBy === "probability") {
        grouped.sort((a, b) => {
          const maxA = Math.max(...a.branches.map(r => r.admission_probability !== null && r.admission_probability !== undefined ? r.admission_probability : 0), 0);
          const maxB = Math.max(...b.branches.map(r => r.admission_probability !== null && r.admission_probability !== undefined ? r.admission_probability : 0), 0);
          return maxB - maxA;
        });
      } else if (state.sortBy === "rank") {
        grouped.sort((a, b) => {
          const minA = Math.min(...a.branches.map(r => r.closing_rank !== null && r.closing_rank !== undefined ? r.closing_rank : Infinity), Infinity);
          const minB = Math.min(...b.branches.map(r => r.closing_rank !== null && r.closing_rank !== undefined ? r.closing_rank : Infinity), Infinity);
          return minA - minB;
        });
      } else if (state.sortBy === "college") {
        grouped.sort((a, b) => a.institute.localeCompare(b.institute));
      }

      grouped.forEach((group) => {
        if (state.sortBy === "probability") {
          group.branches.sort((a, b) => {
            const valA = a.admission_probability !== null && a.admission_probability !== undefined ? a.admission_probability : 0;
            const valB = b.admission_probability !== null && b.admission_probability !== undefined ? b.admission_probability : 0;
            return valB - valA;
          });
        } else if (state.sortBy === "rank") {
          group.branches.sort((a, b) => {
            const valA = a.closing_rank !== null && a.closing_rank !== undefined ? a.closing_rank : Infinity;
            const valB = b.closing_rank !== null && b.closing_rank !== undefined ? b.closing_rank : Infinity;
            return valA - valB;
          });
        } else if (state.sortBy === "college") {
          group.branches.sort((a, b) => a.branch.localeCompare(b.branch));
        }
      });

      contentHtml = `<div class="cards">${grouped.map((g, i) => collegeCardHtml(g, catName, i)).join("")}</div>`;
    } else {
      contentHtml = `<div class="cards">${sortedVisible.map((r, i) => cardHtml(r, i)).join("")}</div>`;
    }

    const isSectionCollapsed = !!state.collapsedSections[catName];
    section.innerHTML = `
      <div class="rsection__head">
        <h2 class="rsection__title">
          <span class="dot dot--${catName.toLowerCase()}" aria-hidden="true"></span>
          ${meta.title} <span class="rsection__count">· ${meta.sub} · ${visible.length}</span>
        </h2>
        <button type="button" class="rsection__toggle-btn" 
                aria-expanded="${!isSectionCollapsed}" 
                aria-controls="cards-${catName.toLowerCase()}" 
                onclick="toggleSection('${catName}')">
          <span class="rsection__toggle-text">${isSectionCollapsed ? t("results.expand") : t("results.collapse")}</span>
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

  const hasResults = recs.length > 0;
  $("empty-results").hidden = hasResults;
  $("empty-filtered").hidden = !hasResults || anyShown;
  $("toolbar").style.display = hasResults ? "" : "none";
  $("spectrum").style.display = hasResults ? "" : "none";
  const specHeader = $("spectrum-header");
  if (specHeader) {
    specHeader.style.display = hasResults ? "flex" : "none";
  }
}

window.toggleSection = function(catName) {
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
      if (textEl) {
        textEl.textContent = isExpanded ? t("results.collapse") : t("results.expand");
      }
    }
  }
  updateExpandAllButtonUI();
};

window.updateExpandAllButtonUI = function() {
  const btn = $("expand-collapse-all-btn");
  if (!btn) return;

  const data = state.lastData;
  const recs = data?.recommendations || [];
  let hasAnyExpanded = false;

  for (const catName of SECTION_ORDER) {
    const all = recs.filter((r) => r.category === catName);
    if (all.length === 0) continue;
    const visible = all.filter(recPassesFilters);
    if (visible.length === 0) continue;

    if (!state.collapsedSections[catName]) {
      hasAnyExpanded = true;
      break;
    }
  }

  btn.textContent = hasAnyExpanded ? t("results.collapseAll") : t("results.expandAll");
  btn.dataset.action = hasAnyExpanded ? "collapse" : "expand";
};

function buildSortOptions() {
  const sortSel = $("results-sort");
  if (!sortSel) return;
  const prev = sortSel.value || state.sortBy || "rank";
  sortSel.innerHTML = "";

  const options = [
    { value: "category", labelKey: "results.sortCategory" },
    { value: "probability", labelKey: "results.sortProbability" },
    { value: "rank", labelKey: "results.sortRank" },
    { value: "college", labelKey: "results.sortCollege" }
  ];

  options.forEach((opt) => {
    const el = document.createElement("option");
    el.value = opt.value;
    el.textContent = t(opt.labelKey);
    sortSel.appendChild(el);
  });

  sortSel.value = prev;
}

function renderResults(data, { keepFilters = false } = {}) {
  if (!keepFilters) {
    state.filterText = "";
    state.filterTypes = [];
    state.sortBy = "rank";
    state.filterRegion = "all";
    state.filterState = "all";
    state.collapsedSections = { Safe: false, Target: false, Reach: false };
    state.expandedColleges = {};
    $("filter-search").value = "";
    document.querySelectorAll("#type-chips .chip").forEach((c) =>
      c.classList.toggle("is-active", c.dataset.type === "")
    );
    if ($("filter-region")) $("filter-region").value = "all";
    if ($("filter-state")) $("filter-state").value = "all";
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

// ── Language switching ────────────────────────────────────────────────────

// Re-apply translations to everything currently on screen. Static markup is
// handled by applyStaticI18n(); the rest (JS-rendered) is rebuilt here.
function refreshDynamicI18n() {
  // Preserve the goal selection across the rebuild.
  buildGoalCards();
  updateGenderNote();
  const ph = $("home-state-placeholder");
  if (ph) ph.textContent = t("flow.statePlaceholder");
  if (state.meta) {
    buildCategoryOptions();
    buildPanelControls();
    syncPanelFromState();
  }
  buildSortOptions();
  $("flow-next").textContent = stepButtonLabel(state.step);
  if (state.step === TOTAL_STEPS - 1) renderReview();
  if (loadingTimer) {
    const ls = loadingLines();
    $("loading-text").textContent = ls[0];
  }
}

function applyLanguage(lang, { rerun = true } = {}) {
  setLang(lang);
  const select = $("lang-select");
  if (select) select.value = lang;
  applyStaticI18n();
  refreshDynamicI18n();

  // If results are on screen, re-fetch so backend-generated text (guidance,
  // notes, reasons …) comes back in the new language. Falls back to a local
  // re-render if we are offline / have no payload.
  if ($("view-results").classList.contains("is-active") && state.lastPayload) {
    state.lastPayload.lang = lang;
    if (rerun) {
      runRequest(state.lastPayload, { keepFilters: true });
    } else if (state.lastData) {
      renderResults(state.lastData, { keepFilters: true });
    }
  }
}

// ── Share / copy link / print ─────────────────────────────────────────────

// Encode the student's inputs into a shareable, stateless query string so the
// link reopens the SAME results (parsed on load by maybeRunFromQuery()).
function buildShareUrl() {
  const params = new URLSearchParams();

  // 1. Current step/view
  let currentStep = "welcome";
  if ($("view-results").classList.contains("is-active")) {
    currentStep = "results";
  } else if ($("view-flow").classList.contains("is-active")) {
    currentStep = String(state.step);
  }
  params.set("step", currentStep);

  // 2. JEE Main rank
  const mains = parseRankInput($("mains-rank"));
  if (mains !== null) params.set("m", String(mains));

  // 3. JEE Advanced rank
  const adv = parseRankInput($("adv-rank"));
  if (adv !== null) params.set("a", String(adv));

  // 4. gender
  if (state.gender) params.set("g", state.gender);

  // 5. category
  const cat = $("seat-category").value || "OPEN";
  params.set("cat", cat);

  // 6. home state
  const hs = $("home-state").value;
  if (hs) params.set("s", hs);

  // 7. career goal
  if (state.goal) params.set("goal", state.goal);

  // 8. branch preference
  if (state.branchPrefs && state.branchPrefs.length) {
    params.set("b", state.branchPrefs.join(","));
  }

  // 9. region filter
  if (state.filterRegion && state.filterRegion !== "all") {
    params.set("region", state.filterRegion);
  }

  // State filter
  if (state.filterState && state.filterState !== "all") {
    params.set("inst_state", state.filterState);
  }

  // 10. college vs branch priority (slider value)
  if (state.brandBranchRatio !== undefined && state.brandBranchRatio !== null) {
    params.set("ratio", String(state.brandBranchRatio));
  }

  // 11. text search filter and chip type filter
  if (state.filterText) {
    params.set("q", state.filterText);
  }
  if (state.filterTypes && state.filterTypes.length > 0) {
    params.set("t", state.filterTypes.join(","));
  }

  params.set("lang", getLang());

  const base = `${location.origin}${location.pathname}`;
  return `${base}?${params.toString()}`;
}

function saveStateToURL() {
  if (!initialStateLoaded) return;
  const newUrl = buildShareUrl();
  history.replaceState(null, "", newUrl);
}

function restoreScrollPosition() {
  const saved = sessionStorage.getItem("disha_scroll_y");
  if (saved !== null) {
    setTimeout(() => {
      window.scrollTo(0, parseFloat(saved));
    }, 100);
  }
}

function loadStateFromURL() {
  const q = new URLSearchParams(location.search);
  const hasParams = [...q.keys()].length > 0;

  if (!hasParams) {
    initialStateLoaded = true;
    return false;
  }

  const lang = q.get("lang");
  if (lang === "en" || lang === "hi") applyLanguage(lang, { rerun: false });

  // Restore ranks
  const mains = parseInt(q.get("m") || "", 10);
  const adv = parseInt(q.get("a") || "", 10);
  const hasMains = Number.isFinite(mains) && mains > 0;
  const hasAdv = Number.isFinite(adv) && adv > 0;

  $("mains-rank").value = hasMains ? fmt(mains) : "";
  $("adv-rank").value = hasAdv ? fmt(adv) : "";

  // Restore gender
  const gender = q.get("g");
  if (gender && ["male", "female", "other"].includes(gender)) {
    state.gender = gender;
    syncGenderRows();
    updateGenderNote();
  }

  // Restore category
  const cat = q.get("cat") || "OPEN";
  if ($("seat-category").querySelector(`option[value="${CSS.escape(cat)}"]`)) {
    $("seat-category").value = cat;
  }

  // Restore home state
  const stateVal = q.get("s") || "";
  if (stateVal && $("home-state").querySelector(`option[value="${CSS.escape(stateVal)}"]`)) {
    $("home-state").value = stateVal;
  }

  // Restore goal
  const goal = q.get("goal");
  if (goal && GOAL_IDS.includes(goal)) {
    state.goal = goal;
    buildGoalCards();
  }

  // Restore branch preferences
  const valid = new Set(branchOptions().map((o) => o.value));
  state.branchPrefs = (q.get("b") || "")
    .split(",")
    .map((v) => v.trim())
    .filter((v) => valid.has(v));
  renderBranchGrids();

  // Restore region filter
  const region = q.get("region") || "all";
  state.filterRegion = region;
  if ($("filter-region")) {
    $("filter-region").value = region;
  }

  // Restore state filter
  const instState = q.get("inst_state") || "all";
  state.filterState = instState;
  if ($("filter-state")) {
    $("filter-state").value = instState;
  }

  // Restore college vs branch priority (slider)
  const ratio = q.get("ratio");
  if (ratio !== null) {
    const parsedRatio = parseFloat(ratio);
    if (!isNaN(parsedRatio)) {
      state.brandBranchRatio = parsedRatio;
    }
  }

  // Restore filter text & type
  const filterText = q.get("q") || "";
  state.filterText = filterText.toLowerCase();
  $("filter-search").value = filterText;

  const filterTypeStr = q.get("t") || "";
  state.filterTypes = filterTypeStr ? filterTypeStr.split(",") : [];
  document.querySelectorAll("#type-chips .chip").forEach((c) => {
    if (state.filterTypes.length === 0) {
      c.classList.toggle("is-active", c.dataset.type === "");
    } else {
      c.classList.toggle("is-active", state.filterTypes.includes(c.dataset.type));
    }
  });

  // Synchronize elements to make sure panel and flow inputs match
  syncPanelFromState();

  // Determine target view / step
  const stepParam = q.get("step");
  if (stepParam === "results" || (!stepParam && (hasMains || hasAdv))) {
    const payload = buildPayload();
    state.lastPayload = payload;
    runRequest(payload, { keepFilters: true }).then(() => {
      restoreScrollPosition();
    });
  } else {
    const stepNum = parseInt(stepParam, 10);
    if (Number.isInteger(stepNum) && stepNum >= 0 && stepNum < TOTAL_STEPS) {
      showView("flow");
      goToStep(stepNum);
      restoreScrollPosition();
    } else if (stepParam === "welcome") {
      showView("welcome");
      restoreScrollPosition();
    } else {
      showView("welcome");
      restoreScrollPosition();
    }
  }

  initialStateLoaded = true;
  return true;
}

function topPicksSummary(limit) {
  const recs = state.lastData?.recommendations || [];
  const targets = recs.filter((r) => r.category === "Target");
  const pool = (targets.length ? targets : recs).slice(0, limit);
  return pool.map((r) => `${r.institute_type} ${r.branch}`);
}

function buildShareText() {
  const counts = state.lastData?.counts?.by_category || {};
  const lines = [t("share.title")];
  const picks = topPicksSummary(3);
  const targetCount = counts.Target || 0;
  if (targetCount > 0 && picks.length) {
    lines.push(t("share.targetLine", { count: targetCount, picks: picks.join(", ") }));
  } else if (picks.length) {
    lines.push(t("share.noTarget", { picks: picks.join(", ") }));
  }
  lines.push(t("share.countsLine", { safe: counts.Safe || 0, reach: counts.Reach || 0 }));
  lines.push("");
  lines.push(t("share.open"));
  lines.push(buildShareUrl());
  return lines.join("\n");
}

function shareToWhatsApp() {
  const text = buildShareText();
  const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank", "noopener");
}

async function copyShareLink() {
  const url = buildShareUrl();
  const label = $("copy-link-label");
  const original = t("results.copyLink");
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(url);
    } else {
      const ta = document.createElement("textarea");
      ta.value = url;
      ta.setAttribute("readonly", "");
      ta.style.position = "absolute";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    label.textContent = t("results.copied");
    setTimeout(() => { label.textContent = original; }, 1800);
  } catch {
    label.textContent = original;
    alert(t("share.copyFail"));
  }
}

// ── Service worker (PWA-lite) ──────────────────────────────────────────────

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  if (location.protocol === "file:") return;
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("sw.js")
      .then((reg) => {
        reg.addEventListener("updatefound", () => {
          const worker = reg.installing;
          if (!worker) return;
          worker.addEventListener("statechange", () => {
            if (worker.state === "activated" && navigator.serviceWorker.controller) {
              window.location.reload();
            }
          });
        });
      })
      .catch(() => { /* non-fatal */ });
  });
}

// ── Events ──────────────────────────────────────────────────────────────

// Live panel wiring: the toggle (mobile collapse) plus every control mirrors
// its value back to the flow inputs / state and triggers a debounced refresh.
function bindPanelEvents() {
  const toggle = $("panel-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const panel = $("results-panel");
      const open = panel.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  const mirrorRank = (panelEl, flowEl) => {
    if (!panelEl || !flowEl) return;
    panelEl.addEventListener("input", () => {
      const n = parseRankInput(panelEl);
      panelEl.value = n === null ? "" : fmt(n);
      flowEl.value = panelEl.value;
      schedulePanelUpdate();
      saveStateToURL();
    });
  };
  mirrorRank($("panel-mains-rank"), $("mains-rank"));
  mirrorRank($("panel-adv-rank"), $("adv-rank"));

  const panelState = $("panel-home-state");
  if (panelState) {
    panelState.addEventListener("change", () => {
      $("home-state").value = panelState.value;
      schedulePanelUpdate();
      saveStateToURL();
    });
  }

  const panelCat = $("panel-seat-category");
  if (panelCat) {
    panelCat.addEventListener("change", () => {
      $("seat-category").value = panelCat.value;
      schedulePanelUpdate();
      saveStateToURL();
    });
    const panelGoal = $("panel-goal");
    if (panelGoal) {
      panelGoal.addEventListener("change", () => {
        state.goal = panelGoal.value;
        buildGoalCards();           // keep the flow's goal cards in sync
        updatePriorityStateUI();
        schedulePanelUpdate();
        saveStateToURL();
      });
    }

    // panel-family-income event listener removed to focus on admission probability insights.

    const priorityToggle = $("priority-toggle");
    if (priorityToggle) {
      priorityToggle.addEventListener("click", (e) => {
        const btn = e.target.closest(".view-toggle-btn");
        if (!btn) return;
        const ratioVal = parseFloat(btn.dataset.ratio);
        state.brandBranchRatio = ratioVal;
        
        updatePriorityStateUI();

        schedulePanelUpdate();
        saveStateToURL();
      });
    }

    const goalFocusBtn = $("priority-goal-focus");
    if (goalFocusBtn) {
      goalFocusBtn.addEventListener("click", () => {
        const pg = $("panel-goal");
        if (pg) {
          pg.focus();
          pg.style.outline = "2px solid #eab308";
          pg.style.boxShadow = "0 0 10px rgba(234, 179, 8, 0.5)";
          setTimeout(() => {
            pg.style.outline = "";
            pg.style.boxShadow = "";
          }, 1500);
        }
      });
    }

    const panelRegion = $("filter-region");
    if (panelRegion) {
      panelRegion.addEventListener("change", () => {
        state.filterRegion = panelRegion.value;
        renderSections();           // region filter runs completely client-side!
        saveStateToURL();
      });
    }
  }
}

function bindEvents() {
  $("begin-btn").addEventListener("click", () => {
    showView("flow");
    goToStep(0);
  });

  $("retry-meta-btn").addEventListener("click", loadMeta);

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
  $("wordmark").addEventListener("click", (e) => {
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
  $("empty-edit-btn").addEventListener("click", backToReview);

  bindPanelEvents();

  const trigger = $("choice-list-trigger");
  if (trigger) {
    trigger.addEventListener("click", () => {
      $("choice-drawer").hidden = false;
      renderChoiceDrawerList();
    });
  }

  const closeBtn = $("choice-drawer-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      $("choice-drawer").hidden = true;
    });
  }

  const overlay = $("choice-drawer-overlay");
  if (overlay) {
    overlay.addEventListener("click", () => {
      $("choice-drawer").hidden = true;
    });
  }

  const csvBtn = $("choice-export-csv");
  if (csvBtn) {
    csvBtn.addEventListener("click", exportChoicesCSV);
  }

  const pdfBtn = $("choice-export-pdf");
  if (pdfBtn) {
    pdfBtn.addEventListener("click", printChoices);
  }

  const clearAllBtn = $("choice-clear-all");
  if (clearAllBtn) {
    clearAllBtn.addEventListener("click", clearChoices);
  }

  $("filter-search").addEventListener("input", (e) => {
    state.filterText = e.target.value.trim().toLowerCase();
    renderSections();
    saveStateToURL();
  });

  const filterState = $("filter-state");
  if (filterState) {
    filterState.addEventListener("change", () => {
      state.filterState = filterState.value;
      renderSections();
      saveStateToURL();
    });
  }

  $("type-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    const type = chip.dataset.type;
    if (type === "") {
      state.filterTypes = [];
    } else {
      const idx = state.filterTypes.indexOf(type);
      if (idx >= 0) state.filterTypes.splice(idx, 1);
      else state.filterTypes.push(type);
    }
    document.querySelectorAll("#type-chips .chip").forEach((c) => {
      if (state.filterTypes.length === 0) {
        c.classList.toggle("is-active", c.dataset.type === "");
      } else {
        c.classList.toggle("is-active", state.filterTypes.includes(c.dataset.type));
      }
    });
    renderSections();
    saveStateToURL();
  });

  $("clear-filters-btn").addEventListener("click", () => {
    state.filterText = "";
    state.filterTypes = [];
    state.filterRegion = "all";
    state.filterState = "all";
    $("filter-search").value = "";
    if ($("filter-region")) $("filter-region").value = "all";
    if ($("filter-state")) $("filter-state").value = "all";
    document.querySelectorAll("#type-chips .chip").forEach((c) =>
      c.classList.toggle("is-active", c.dataset.type === "")
    );
    renderSections();
    saveStateToURL();
  });

  const expColAllBtn = $("expand-collapse-all-btn");
  if (expColAllBtn) {
    expColAllBtn.addEventListener("click", () => {
      const action = expColAllBtn.dataset.action || "collapse";
      const shouldCollapse = action === "collapse";

      for (const catName of SECTION_ORDER) {
        state.collapsedSections[catName] = shouldCollapse;

        const sectionId = `section-${catName.toLowerCase()}`;
        const sectionEl = $(sectionId);
        if (sectionEl) {
          const btn = sectionEl.querySelector(".rsection__toggle-btn");
          const collapseEl = sectionEl.querySelector(".rsection__collapse");
          if (btn && collapseEl) {
            btn.setAttribute("aria-expanded", String(!shouldCollapse));
            collapseEl.classList.toggle("is-collapsed", shouldCollapse);
            const textEl = btn.querySelector(".rsection__toggle-text");
            if (textEl) {
              textEl.textContent = shouldCollapse ? t("results.expand") : t("results.collapse");
            }
          }
        }
      }

      updateExpandAllButtonUI();
    });
  }

  $("home-state").addEventListener("change", () => {
    saveStateToURL();
  });

  $("seat-category").addEventListener("change", () => {
    saveStateToURL();
  });

  const btnBranch = $("view-by-branch");
  const btnCollege = $("view-by-college");
  if (btnBranch && btnCollege) {
    btnBranch.addEventListener("click", () => {
      if (state.view !== "branch") {
        state.view = "branch";
        localStorage.setItem("disha_view", "branch");
        syncViewToggleUI();
        renderSections();
      }
    });
    btnCollege.addEventListener("click", () => {
      if (state.view !== "college") {
        state.view = "college";
        localStorage.setItem("disha_view", "college");
        syncViewToggleUI();
        renderSections();
      }
    });
  }

  const sortSel = $("results-sort");
  if (sortSel) {
    sortSel.addEventListener("change", (e) => {
      state.sortBy = e.target.value;
      renderSections();
    });
  }

  $("spectrum").addEventListener("click", (e) => {
    const zone = e.target.closest(".zone");
    if (!zone) return;
    const target = $(`section-${zone.dataset.zone.toLowerCase()}`);
    if (target) target.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "start" });
  });

  const langSelect = $("lang-select");
  if (langSelect) {
    langSelect.value = getLang();
    langSelect.addEventListener("change", (e) => applyLanguage(e.target.value));
  }
  $("share-btn").addEventListener("click", shareToWhatsApp);
  $("copy-link-btn").addEventListener("click", copyShareLink);
  $("print-btn").addEventListener("click", () => {
    // Families review the full grouped list, so clear any active filters first.
    if (state.filterText || state.filterTypes.length > 0) {
      state.filterText = "";
      state.filterTypes = [];
      $("filter-search").value = "";
      document.querySelectorAll("#type-chips .chip").forEach((c) =>
        c.classList.toggle("is-active", c.dataset.type === "")
      );
      renderSections();
    }
    window.print();
  });
}

// ── Init ────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  setLang(getLang());                 // sync <html lang> + persist default
  applyStaticI18n();                  // translate all static markup once
  const langSelect = $("lang-select");
  if (langSelect) langSelect.value = getLang();

  attachRankFormatting($("mains-rank"));
  attachRankFormatting($("adv-rank"));
  bindGenderRow();
  // bindFamilyIncomeRow() removed to focus on admission probability insights.
  buildGoalCards();
  bindEvents();
  bindRulerTooltip();
  registerServiceWorker();

  // Wire scroll position persistence on beforeunload
  window.addEventListener("beforeunload", () => {
    sessionStorage.setItem("disha_scroll_y", String(window.scrollY));
  });

  // Determine initial view: show loading if URL has parameters, otherwise welcome
  const hasParams = [...new URLSearchParams(location.search).keys()].length > 0;
  if (hasParams) {
    showView("loading");
  } else {
    showView("welcome");
  }

  // Load form metadata, then load state from URL if present
  loadMeta().then(() => {
    const restored = loadStateFromURL();
    if (!restored) {
      showView("welcome");
    }
  });
});
