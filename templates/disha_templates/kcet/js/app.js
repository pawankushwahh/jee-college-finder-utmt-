"use strict";

/* ═══════════════════════════════════════════════════════════════
   Disha — KCET (standalone SPA, NO shared JEE code)

   View IDs (each step is its own <section>):
     view-welcome  view-step-0  view-step-1  view-step-2  view-step-3
     view-loading  view-results  view-error

   API:  GET  /api/kcet/meta
         POST /api/kcet/recommend
   ═══════════════════════════════════════════════════════════════ */

// ── GOALS ─────────────────────────────────────────────────────

const GOALS = [
  { id: "coding",       name: "CS / Software / AI",         desc: "Computer Science, IT, AI, Data Science" },
  { id: "core",         name: "Core Engineering",            desc: "Mechanical, Civil, Electrical, Chemical" },
  { id: "research",     name: "Research / Biotech",          desc: "Biotechnology, Aerospace, Sciences" },
  { id: "pure_science", name: "Physics / Chemistry / Maths", desc: "Pure science foundations" },
  { id: "mba",          name: "Management / MBA later",      desc: "Any branch — brand & placement focus" },
  { id: "undecided",    name: "Not sure yet",                desc: "Show me all good options" },
];

const GOAL_ICONS = {
  coding:      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  core:        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
  research:    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg>',
  pure_science:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v8L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45L14 10V2z"/><path d="M8.5 2h7"/><path d="M7 16h10"/></svg>',
  mba:         '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>',
  undecided:   '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
};

// ── ALL VIEW IDs ───────────────────────────────────────────────
const ALL_VIEWS = [
  "welcome", "step-0", "step-1", "step-2", "step-3",
  "loading", "results", "error",
];

// ── STATE ─────────────────────────────────────────────────────
const state = {
  rank:     null,
  quota:    "GM",
  goal:     "undecided",
  lastData: null,
  filterText: "",
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

// ── QUOTA ─────────────────────────────────────────────────────
function syncQuota() {
  const s1 = $("quota-select");
  if (s1) s1.value = state.quota;
  const s2 = $("panel-quota-select");
  if (s2) s2.value = state.quota;
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
      // Auto-advance after 260 ms so selection is visually confirmed
      setTimeout(() => goToStep(3), 260);
    });
    grid.appendChild(btn);
  }
}

function syncPanelGoal() {
  const sel = $("panel-goal");
  if (sel) sel.value = state.goal;
}

// ── REVIEW (STEP 3) ───────────────────────────────────────────
function populateReview() {
  const rv = $("rv-rank-val");
  const qv = $("rv-quota-val");
  const gv = $("rv-goal-val");
  if (rv) rv.textContent = state.rank ? fmt(state.rank) : "—";
  if (qv) qv.textContent = state.quota;
  if (gv) gv.textContent = GOALS.find(g => g.id === state.goal)?.name || state.goal;
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
      body: JSON.stringify({
        rank:      state.rank,
        quota:     state.quota,
        goal:      state.goal,
        bucket:    "all",
        page:      1,
        page_size: 150,
      }),
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
  state.rank  = r;
  state.quota = $("panel-quota-select")?.value || state.quota;
  state.goal  = $("panel-goal")?.value || state.goal;
  try {
    const data = await apiRequest("/api/kcet/recommend", {
      method: "POST",
      body: JSON.stringify({
        rank: state.rank, quota: state.quota, goal: state.goal,
        bucket: "all", page: 1, page_size: 150,
      }),
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
  syncQuota();
  syncPanelGoal();
}

// ── RESULTS ───────────────────────────────────────────────────
const SEC_ORDER   = ["Target", "Reach", "Safe"];
const SEC_DISPLAY = { Safe: "Safe", Target: "Target", Reach: "Dream" };
const SEC_TONE    = { Safe: "safe", Target: "target", Reach: "reach" };

function renderResults(data, { keepFilter = false } = {}) {
  if (!keepFilter) state.filterText = "";

  // Profile chips
  const chips = $("profile-chips");
  if (chips) {
    chips.innerHTML = [
      `Rank <strong>${fmt(state.rank)}</strong>`,
      esc(state.quota),
      esc(GOALS.find(g => g.id === state.goal)?.name || state.goal),
    ].map(c => `<span class="pchip">${c}</span>`).join("");
  }

  // Headline
  const ts = data.total_safe   || 0;
  const tt = data.total_target || 0;
  const tr = data.total_reach  || 0;
  const total = ts + tt + tr;

  // Active filter alert
  const toast = $("filter-toast");
  const toastGoal = $("toast-goal-name");
  if (toast && toastGoal) {
    if (state.goal !== "undecided" || state.filterText) {
      toastGoal.textContent = GOALS.find(g => g.id === state.goal)?.name || state.goal;
      toast.hidden = false;
    } else {
      toast.hidden = true;
    }
  }

  // Cards
  const grouped = {
    Safe:   (data.safe   || []).map(r => ({ ...r, category: "Safe"   })),
    Target: (data.target || []).map(r => ({ ...r, category: "Target" })),
    Reach:  (data.reach  || []).map(r => ({ ...r, category: "Reach"  })),
  };

  const q = state.filterText.toLowerCase();
  if (q) {
    for (const cat of SEC_ORDER) {
      grouped[cat] = grouped[cat].filter(r =>
        r.institute.toLowerCase().includes(q) || r.program.toLowerCase().includes(q)
      );
    }
  }

  const totals = { Safe: ts, Target: tt, Reach: tr };
  const container = $("results-sections-container");
  if (!container) return;

  if (total === 0) {
    container.innerHTML = `<div class="rsection__empty">No colleges match your criteria. Try entering a different rank or checking another category.</div>`;
    return;
  }

  container.innerHTML = SEC_ORDER.map(cat => {
    const items  = grouped[cat];
    const count  = totals[cat];
    const tone   = SEC_TONE[cat];
    const label  = SEC_DISPLAY[cat];

    const content = items.length === 0
      ? `<p class="rsection__empty">${
          count === 0 ? "No programs in this category for your rank."
          : q ? "No results match your search here."
          : "Results loading…"
        }</p>`
      : items.map((r, i) => makeCard(r, i)).join("");

    return `
      <section class="rsection" id="section-${cat.toLowerCase()}">
        <div class="rsection__head">
          <span class="rsection__tag tone-${tone}">${label}</span>
          <span class="rsection__count">${fmt(count)} program${count !== 1 ? "s" : ""}</span>
        </div>
        <div class="rsection__collapse" id="collapse-${cat.toLowerCase()}">
          <div class="rsection__collapse-inner">
            ${content}
          </div>
        </div>
      </section>`;
  }).join("");
}

// ── CARD ──────────────────────────────────────────────────────
function makeCard(rec, idx) {
  const catL  = rec.category === "Reach" ? "reach" : rec.category.toLowerCase();
  const delay = Math.min(idx * 40, 400);
  const rank  = state.rank;
  const cut   = Math.round(rec.cutoff_rank);

  // Position the cutoff and your rank on a linear track
  const lo  = Math.min(rank, cut) * 0.75;
  const hi  = Math.max(rank, cut) * 1.25 || 1;
  const pos = (v) => {
    const range = hi - lo;
    if (range <= 0) return 50;
    return Math.min(Math.max(((v - lo) / range) * 100, 3), 97);
  };
  const cutPos = pos(cut);
  const youPos = pos(rank);

  // Window spans from whichever is lower to whichever is higher
  const winLeft  = Math.min(cutPos, youPos);
  const winRight = Math.max(cutPos, youPos);

  // Verdict sentence
  let verdict;
  if (rec.category === "Safe") {
    verdict = `Your rank (${fmt(rank)}) is better than the cutoff by ${fmt(cut - rank)} — very likely admission.`;
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

  const star = (rec.category === "Target" || rec.category === "Safe")
    ? `<span class="ccard__star" title="Fits your stated goal">
         <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8L12 2z"/></svg>
         fits your goal</span>`
    : "";

  return `
    <article class="ccard ccard--${catL}" style="animation-delay:${delay}ms">
      <div class="ccard__meta">
        <span class="tag tag--govt">KEA</span>
        <span class="tag">KARNATAKA</span>
        <span class="tag">${esc(rec.quota)}</span>
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
        <p class="rankbar__verdict">${verdict}</p>
      </div>

      <div class="ccard__foot">
        <span>${esc(rec.quota)} seat</span><span>via KCET 2025</span><span>Official cutoff</span>
      </div>
    </article>`;
}

// ── META ──────────────────────────────────────────────────────
async function loadMeta() {
  try {
    const meta = await apiRequest("/api/kcet/meta");
    const note = $("data-note");
    if (note) note.textContent = `KCET 2025 · ${fmt(meta.total_programs)} programs`;
    
    // Populate quota select dropdowns
    const q1 = $("quota-select");
    const q2 = $("panel-quota-select");
    if (meta.quotas && meta.quotas.length) {
      const quotaOptions = meta.quotas.map(q => `<option value="${q}">${q}</option>`).join("");
      if (q1) q1.innerHTML = quotaOptions;
      if (q2) q2.innerHTML = quotaOptions;
      
      if (!meta.quotas.includes(state.quota)) {
        state.quota = meta.quotas[0];
      }
      syncQuota();
    }

    buildGoalGrid();
    // Build panel goal select
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
  // Welcome → step 0
  $("begin-btn")?.addEventListener("click", () => goToStep(0));

  // Restart
  $("restart-btn")?.addEventListener("click", () => {
    state.rank = null; state.quota = "GM"; state.goal = "undecided";
    syncQuota();
    showView("welcome");
  });

  // Step 0: rank input
  fmtRankInput($("kcet-rank"));
  $("kcet-rank")?.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); validateAndNext0(); }
  });
  $("next-0")?.addEventListener("click", validateAndNext0);
  $("back-0")?.addEventListener("click", () => showView("welcome"));

  // Step 1: quota select
  $("quota-select")?.addEventListener("change", e => {
    state.quota = e.target.value;
    syncQuota();
  });
  $("next-1")?.addEventListener("click", () => goToStep(2));
  $("back-1")?.addEventListener("click", () => goToStep(0));

  // Step 2: goal (auto-advances on selection)
  $("back-2")?.addEventListener("click", () => goToStep(1));

  // Step 3: review / confirm
  $("back-3")?.addEventListener("click", () => goToStep(2));
  $("see-colleges-btn")?.addEventListener("click", submitProfile);

  // Review rows → jump back to specific step
  $("rv-rank") ?.addEventListener("click",  () => goToStep(0));
  $("rv-quota")?.addEventListener("click",  () => goToStep(1));
  $("rv-goal") ?.addEventListener("click",  () => goToStep(2));

  // Error page
  $("retry-btn")    ?.addEventListener("click", submitProfile);
  $("error-edit-btn")?.addEventListener("click", () => goToStep(0));

  // Panel
  fmtRankInput($("panel-rank"));
  $("panel-rank")?.addEventListener("input", schedulePanelUpdate);
  $("panel-quota-select")?.addEventListener("change", e => {
    state.quota = e.target.value;
    schedulePanelUpdate();
  });
  $("panel-goal")?.addEventListener("change", () => {
    state.goal = $("panel-goal").value;
    schedulePanelUpdate();
  });

  // Panel toggle (mobile)
  const pt = $("panel-toggle");
  const pb = $("panel-body");
  pt?.addEventListener("click", () => {
    const open = pt.getAttribute("aria-expanded") === "true";
    pt.setAttribute("aria-expanded", open ? "false" : "true");
    pb?.classList.toggle("is-open", !open);
  });

  // Filter search
  $("results-search-input")?.addEventListener("input", e => {
    state.filterText = e.target.value;
    if (state.lastData) renderResults(state.lastData, { keepFilter: true });
  });

  // Clear toast btn
  $("toast-clear-btn")?.addEventListener("click", () => {
    state.goal = "undecided";
    state.filterText = "";
    const searchIn = $("results-search-input");
    if (searchIn) searchIn.value = "";
    syncPanel();
    schedulePanelUpdate();
  });

  // Share
  $("share-btn")?.addEventListener("click", () => {
    const msg = `My KCET rank ${fmt(state.rank)} (${state.quota}). Check out Disha for free college predictions → ${location.href}`;
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
