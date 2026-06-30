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
  mba: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>',
  core: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
  undecided: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
};

const GOAL_IDS = ["coding", "research", "mba", "core", "undecided"];

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
  goal: null,
  branchPrefs: [],          // selected branch-preference values; [] means "Any"
  lastPayload: null,
  lastData: null,
  filterText: "",
  filterType: "",
  filterRegion: "all",
  choices: JSON.parse(localStorage.getItem("disha_choices") || "[]"),
  // Data source mode: "basic" or "extended".
  // Persisted across sessions; overridden to server default if toggle is hidden.
  dataMode: localStorage.getItem("disha_data_mode") || "basic",
  view: localStorage.getItem("disha_view") || "branch", // "branch" or "college"
  expandedColleges: {}, // in-memory accordion toggle state
};

const TOTAL_STEPS = 6;

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
  if (index === 3) {
    const err = $("error-goal");
    if (!state.goal) {
      err.textContent = t("validation.goal");
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
  const suffix = " — " + t("category.comingSoon");
  return opt.text.endsWith(suffix) ? opt.text.slice(0, -suffix.length).trim() : opt.text;
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
    { key: t("review.goal"), val: escapeHtml(state.goal ? goalName(state.goal) : t("review.dash")), step: 3 },
    { key: t("review.branch"), val: escapeHtml(branchReviewValue()), step: 4 },
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
function initDataModeToggle(meta) {
  const field = $("data-mode-field");
  const basicBtn = $("data-mode-basic");
  const extBtn = $("data-mode-extended");
  const catSel = $("panel-seat-category");
  const catHint = $("panel-category-hint");

  if (!meta.allow_toggle) {
    // Server has locked the mode — hide toggle, force the server default.
    if (field) field.hidden = true;
    state.dataMode = meta.data_mode;
    localStorage.setItem("disha_data_mode", state.dataMode);
    applyDataModeToCategory(state.dataMode, catSel, catHint);
    return;
  }

  // Show the toggle.
  if (field) field.hidden = false;

  // Clamp stored mode to a valid value.
  if (!["basic", "extended"].includes(state.dataMode)) {
    state.dataMode = meta.data_mode || "basic";
  }

  // Reflect current mode on buttons.
  setDataModeUI(state.dataMode, basicBtn, extBtn, catSel, catHint);

  // Wire click handlers.
  [basicBtn, extBtn].forEach((btn) => {
    btn.addEventListener("click", () => {
      const chosen = btn.dataset.mode;
      if (chosen === state.dataMode) return;  // no-op
      state.dataMode = chosen;
      localStorage.setItem("disha_data_mode", chosen);
      setDataModeUI(chosen, basicBtn, extBtn, catSel, catHint);
      // If results are on screen, refresh immediately.
      if (state.lastPayload) {
        const payload = { ...state.lastPayload, data_mode: chosen };
        // Reset category to OPEN when switching back to basic.
        if (chosen === "basic") payload.seat_category = "OPEN";
        state.lastPayload = payload;
        runLiveRequest(payload);
      }
    });
  });
}

function setDataModeUI(mode, basicBtn, extBtn, catSel, catHint) {
  const isExt = mode === "extended";
  basicBtn.setAttribute("aria-pressed", (!isExt).toString());
  extBtn.setAttribute("aria-pressed", isExt.toString());
  applyDataModeToCategory(mode, catSel, catHint);
  // Pulse the category field so the user notices it changed.
  const catField = $("panel-category-field");
  if (catField) {
    catField.classList.remove("field-pulse");
    void catField.offsetWidth; // force reflow to restart animation
    catField.classList.add("field-pulse");
  }
}

function applyDataModeToCategory(mode, catSel, catHint) {
  if (!catSel) return;
  buildCategoryOptions(catSel); // Re-build options so disabled states match the mode!
  if (mode === "extended") {
    catSel.disabled = false;
    if (catHint) catHint.hidden = true;
  } else {
    // Basic: lock to OPEN only.
    catSel.value = "OPEN";
    catSel.disabled = true;
    if (catHint) catHint.hidden = false;
  }
}

// ── Live panel (counsellor dashboard) ─────────────────────────────────────

// Build the editable controls that mirror — and drive — the student profile
// from the results page. Selects/options come from cached meta.
function buildPanelControls() {
  buildPanelGenderRow();
  buildPanelGoalSelect();
  buildPanelStateSelect();
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

    // In extended mode, all categories are available.
    const isAvailable = (state.dataMode === "extended") || c.available;
    opt.textContent = isAvailable ? label : `${label} — ${t("category.comingSoon")}`;
    opt.disabled = !isAvailable;
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
    data_mode: state.dataMode || "basic",
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
    renderResults(data);
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
function syncPanelFromState() {
  if ($("panel-mains-rank")) $("panel-mains-rank").value = $("mains-rank").value;
  if ($("panel-adv-rank")) $("panel-adv-rank").value = $("adv-rank").value;
  if ($("panel-home-state")) $("panel-home-state").value = $("home-state").value;
  if ($("panel-seat-category")) {
    $("panel-seat-category").value = $("seat-category").value || "OPEN";
  }
  if ($("panel-goal") && state.goal) $("panel-goal").value = state.goal;
  if ($("panel-brand-branch-slider")) $("panel-brand-branch-slider").value = state.brandBranchRatio !== undefined ? state.brandBranchRatio : 0.5;
  if ($("panel-region")) $("panel-region").value = state.filterRegion || "all";
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

  // Data source mode badge
  const mode = state.dataMode || "basic";
  const modeBadge = mode === "extended"
    ? `<span class="data-mode-badge data-mode-badge--extended">&#9210; Extended</span>`
    : `<span class="data-mode-badge data-mode-badge--basic">&#9109; Basic</span>`;

  $("profile-chips").innerHTML =
    chips.map((c) => `<span class="pchip">${c}</span>`).join("") +
    `<span class="pchip" style="padding:0">${modeBadge}</span>`;
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
  DESIGN CHOICE — TWO stacked rulers, not one.
  JEE Advanced (IIT) and JEE Main (NIT/IIIT/GFTI) ranks come from different
  exams and different candidate pools, so they sit on separate scales; plotting
  both against a single "YOU" marker would be meaningless. We draw one ruler per
  exam the student actually has a rank for, each with its own YOU line.
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

const RULER_TICKS = [
  { rank: 10, label: "10" },
  { rank: 100, label: "100" },
  { rank: 1000, label: "1K" },
  { rank: 10000, label: "10K" },
  { rank: 100000, label: "1L" },
  { rank: 1000000, label: "10L" },
];

const RULER_GROUPS = [
  { exam: "advanced", titleKey: "ruler.iitTitle", viaKey: "ruler.iitVia", rankKey: "adv_rank" },
  { exam: "mains", titleKey: "ruler.nitTitle", viaKey: "ruler.nitVia", rankKey: "mains_rank" },
];

const RULER_LANES = 4; // vertical jitter lanes to de-clutter dense clusters

function rulerGroupHtml(group, recs) {
  const items = recs.filter((r) => r.exam === group.exam);
  if (!items.length) return "";

  const title = t(group.titleKey);
  const via = t(group.viaKey);
  const youRank = state.lastPayload?.[group.rankKey];
  // sort by closing rank so adjacent (visually overlapping) dots land in
  // different jitter lanes, spreading dense clusters vertically
  const sorted = items.slice().sort((a, b) => a.closing_rank - b.closing_rank);

  const dots = sorted
    .map((r, i) => {
      const cat = r.category.toLowerCase();
      return `<span class="ruler__dot ruler__dot--${cat}" style="left:${rankPos(r.closing_rank).toFixed(2)}%;--lane:${i % RULER_LANES}" data-inst="${escapeHtml(r.institute)}" data-branch="${escapeHtml(r.branch)}" data-rank="${r.closing_rank}" data-cat="${cat}"></span>`;
    })
    .join("");

  const grid = RULER_TICKS.map(
    (t) => `<span class="ruler__grid" style="left:${rankPos(t.rank).toFixed(2)}%"></span>`
  ).join("");

  const scale = RULER_TICKS.map(
    (t) => `<span class="ruler__tick" style="left:${rankPos(t.rank).toFixed(2)}%">${t.label}</span>`
  ).join("");

  const you = youRank
    ? `<div class="ruler__you" style="left:${rankPos(youRank).toFixed(2)}%" title="${escapeHtml(t("ruler.yourRank", { rank: fmt(youRank) }))}"><span class="ruler__you-flag">${escapeHtml(t("ruler.you"))}</span></div>`
    : "";

  const headRight = youRank
    ? `<span class="ruler__you-rank">${escapeHtml(t("ruler.you"))} · ${fmt(youRank)}</span>`
    : `<span class="ruler__count">${items.length} ${escapeHtml(t("ruler.options"))}</span>`;

  const aria = `${title} ${via}: ${items.length}`;

  return `
    <div class="ruler__group" role="img" aria-label="${escapeHtml(aria)}">
      <div class="ruler__head">
        <span class="ruler__title">${escapeHtml(title)} <span class="ruler__via">${escapeHtml(via)}</span></span>
        ${headRight}
      </div>
      <div class="ruler__track">
        ${grid}
        ${dots}
        ${you}
      </div>
      <div class="ruler__scale">${scale}</div>
    </div>`;
}

// Built once per result render (not on filter changes) to keep typing snappy.
function renderRuler(data) {
  const el = $("ruler");
  const recs = data?.recommendations || [];
  const groups = RULER_GROUPS.map((g) => rulerGroupHtml(g, recs)).filter(Boolean).join("");

  if (!groups) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }

  el.innerHTML = `
    <div class="ruler__intro">
      <p class="eyebrow">${escapeHtml(t("ruler.introEyebrow"))}</p>
      <p class="ruler__lede">${escapeHtml(t("ruler.lede"))}</p>
    </div>
    ${groups}
    <div class="ruler__tip" id="ruler-tip" aria-hidden="true"></div>`;
  el.hidden = false;
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
    else hideTip();
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

// Confidence band → human label + tooltip. Colours come from the CSS class.
function confidenceMeta(band) {
  const b = ["high", "medium", "fragile"].includes(band) ? band : "medium";
  return { label: t(`confidence.${b}Label`), hint: t(`confidence.${b}Hint`) };
}

function confidenceChipHtml(rec) {
  const meta = confidenceMeta(rec.confidence);
  return `<span class="conf-chip conf-chip--${escapeHtml(rec.confidence)}" title="${escapeHtml(meta.hint)}">${escapeHtml(meta.label)}</span>`;
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
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
  const recommendations = state.lastData?.recommendations || [];
  const rec = recommendations.find(r => r.institute === institute && r.branch === branch);
  if (!rec) return;

  const idx = state.choices.findIndex(c => c.institute === institute && c.branch === branch);
  if (idx > -1) {
    state.choices.splice(idx, 1);
  } else {
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

function updateChoiceUI() {
  const trigger = $("choice-list-trigger");
  const count = $("choice-count");

  if (count) count.textContent = state.choices.length;

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
      <div class="choice-drawer__handle" aria-label="Drag to reorder">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>
      </div>
      <div class="choice-drawer__item-info">
        <span class="choice-drawer__item-rank">#${idx + 1}</span>
        <div>
          <strong class="choice-drawer__item-inst">${escapeHtml(c.institute)}</strong>
          <span class="choice-drawer__item-branch">${escapeHtml(c.branch)}</span>
        </div>
      </div>
      <button type="button" class="choice-drawer__item-remove" onclick="toggleBookmark(event, null, '${escapeHtml(c.institute)}', '${escapeHtml(c.branch)}')">&times;</button>
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
      `"${c.institute.replace(/"/g, '""')}"`,
      `"${c.branch.replace(/"/g, '""')}"`,
      `"${c.degree.replace(/"/g, '""')}"`
    ];
    if (hasFees) {
      const feeStr = c.estimated_fees > 0 ? `₹${(c.estimated_fees / 1000).toFixed(0)}k/year` : "Free / Fully Waived";
      row.push(`"${feeStr}"`, `"${(c.fee_note || "").replace(/"/g, '""')}"`);
    }
    row.push(`"${c.category}"`);
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
      <td><strong>${escapeHtml(c.institute)}</strong></td>
      <td>${escapeHtml(c.branch)}</td>
      <td>${escapeHtml(c.degree)}</td>
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
  if (state.filterType && rec.institute_type !== state.filterType) return false;
  if (state.filterRegion && state.filterRegion !== "all") {
    if (state.filterRegion === "metro" && !rec.is_metro) return false;
    if (state.filterRegion !== "metro" && rec.region !== state.filterRegion) return false;
  }
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
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
      contentHtml = `<div class="cards">${grouped.map((g, i) => collegeCardHtml(g, catName, i)).join("")}</div>`;
    } else {
      contentHtml = `<div class="cards">${visible.map((r, i) => cardHtml(r, i)).join("")}</div>`;
    }

    section.innerHTML = `
      <div class="rsection__head">
        <h2 class="rsection__title">
          <span class="dot dot--${catName.toLowerCase()}" aria-hidden="true"></span>
          ${meta.title} <span class="rsection__count">· ${meta.sub} · ${visible.length}</span>
        </h2>
      </div>
      ${blurbs[catName] ? `<p class="rsection__blurb">${escapeHtml(blurbs[catName])}</p>` : ""}
      ${contentHtml}`;
    container.appendChild(section);
  }

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

function renderResults(data, { keepFilters = false } = {}) {
  if (!keepFilters) {
    state.filterText = "";
    state.filterType = "";
    $("filter-search").value = "";
    document.querySelectorAll("#type-chips .chip").forEach((c) =>
      c.classList.toggle("is-active", c.dataset.type === "")
    );
  }

  renderProfileChips();
  renderNote(data);
  renderRuler(data);

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
      runRequest(state.lastPayload);
    } else if (state.lastData) {
      renderResults(state.lastData);
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

  // 10. college vs branch priority (slider value)
  if (state.brandBranchRatio !== undefined && state.brandBranchRatio !== null) {
    params.set("ratio", String(state.brandBranchRatio));
  }

  // 11. text search filter and chip type filter
  if (state.filterText) {
    params.set("q", state.filterText);
  }
  if (state.filterType) {
    params.set("t", state.filterType);
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
  if ($("panel-region")) {
    $("panel-region").value = region;
  }

  // Restore college vs branch priority (slider)
  const ratio = q.get("ratio");
  if (ratio !== null) {
    const parsedRatio = parseFloat(ratio);
    if (!isNaN(parsedRatio)) {
      state.brandBranchRatio = parsedRatio;
      if ($("panel-brand-branch-slider")) {
        $("panel-brand-branch-slider").value = ratio;
      }
    }
  }

  // Restore filter text & type
  const filterText = q.get("q") || "";
  state.filterText = filterText.toLowerCase();
  $("filter-search").value = filterText;

  const filterType = q.get("t") || "";
  state.filterType = filterType;
  document.querySelectorAll("#type-chips .chip").forEach((c) =>
    c.classList.toggle("is-active", c.dataset.type === filterType)
  );

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
      .register("/sw.js")
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
        schedulePanelUpdate();
        saveStateToURL();
      });
    }

    // panel-family-income event listener removed to focus on admission probability insights.

    const panelSlider = $("panel-brand-branch-slider");
    if (panelSlider) {
      panelSlider.addEventListener("input", () => {
        state.brandBranchRatio = parseFloat(panelSlider.value);
        schedulePanelUpdate();
        saveStateToURL();
      });
    }

    const panelRegion = $("panel-region");
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

  $("filter-search").addEventListener("input", (e) => {
    state.filterText = e.target.value.trim().toLowerCase();
    renderSections();
    saveStateToURL();
  });

  $("type-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    state.filterType = chip.dataset.type;
    document.querySelectorAll("#type-chips .chip").forEach((c) =>
      c.classList.toggle("is-active", c === chip)
    );
    renderSections();
    saveStateToURL();
  });

  $("clear-filters-btn").addEventListener("click", () => {
    state.filterText = "";
    state.filterType = "";
    $("filter-search").value = "";
    document.querySelectorAll("#type-chips .chip").forEach((c) =>
      c.classList.toggle("is-active", c.dataset.type === "")
    );
    renderSections();
    saveStateToURL();
  });

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
    if (state.filterText || state.filterType) {
      state.filterText = "";
      state.filterType = "";
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
