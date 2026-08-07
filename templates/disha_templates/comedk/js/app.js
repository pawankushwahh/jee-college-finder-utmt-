"use strict";

/* ═══════════════════════════════════════════════════════════════
   Disha — COMEDK  (standalone SPA, NO shared JEE code)

   View IDs (each step is its own <section>):
     view-welcome  view-step-0  view-step-1  view-step-2  view-step-3
     view-loading  view-results  view-error

   API:  GET  /api/comedk/meta
         POST /api/comedk/recommend
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
  ["quota-row", "panel-quota-row"].forEach(rowId => {
    const row = $(rowId);
    if (!row) return;
    row.querySelectorAll(".choice").forEach(btn => {
      const on = btn.dataset.value === state.quota;
      btn.classList.toggle("is-selected", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
  });
}

function bindQuotaRow(rowId, onChange) {
  const row = $(rowId);
  if (!row) return;
  row.addEventListener("click", e => {
    const btn = e.target.closest(".choice");
    if (!btn) return;
    state.quota = btn.dataset.value;
    syncQuota();
    if (onChange) onChange();
  });
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
  if (qv) qv.textContent = state.quota === "GM" ? "GM — General Merit" : "KKR — Kalyana Karnataka";
  if (gv) gv.textContent = GOALS.find(g => g.id === state.goal)?.name || state.goal;
}

// ── NAVIGATION ────────────────────────────────────────────────
function goToStep(n) {
  if (n === 3) populateReview();
  showView(`step-${n}`);
}

// ── LOADING ANIMATION ─────────────────────────────────────────
const LOADING_LINES = [
  "Reading COMEDK 2025 cutoffs…",
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
    const data = await apiRequest("/api/comedk/recommend", {
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
  state.goal  = $("panel-goal")?.value || state.goal;
  try {
    const data = await apiRequest("/api/comedk/recommend", {
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

  const hl = $("note-headline");
  const gd = $("note-guidance");
  const tips = $("note-tips");

  // Dynamic headline matching JEE tone
  if (hl) {
    if (total === 0) {
      hl.textContent = "No programs match this rank and quota.";
    } else if (tt > 0 && ts > 0) {
      hl.textContent = "You're standing in a good spot.";
    } else if (ts > 0) {
      hl.textContent = "You have strong backup options.";
    } else if (tt > 0) {
      hl.textContent = `${fmt(total)} realistic options found.`;
    } else {
      hl.textContent = "These are ambitious picks — worth trying.";
    }
  }

  // Rich guidance paragraph matching JEE format
  if (gd) {
    const goalName = GOALS.find(g => g.id === state.goal)?.name || "all branches";
    if (total > 0) {
      gd.textContent = `Found ${fmt(total)} eligible college–program options for your profile (showing ${fmt(total)}). They are grouped into Target, Dream and Safe, and ordered to match your stated interest.`;
    } else {
      gd.textContent = "Try adjusting your rank or quota to find matching programs.";
    }
  }

  // Tips list (matches JEE's bullet points)
  if (tips) {
    const tipsList = [];
    if (total > 0) {
      tipsList.push("COMEDK colleges offer lateral entry and branch changes after first year based on performance.");
      tipsList.push("Broad branches (CS, ECE, Mechanical, Civil) keep many doors open for future specialisation.");
      tipsList.push("Talk to current students and check NIRF rankings before finalising your choice.");
    }
    tips.innerHTML = tipsList.map(t => `<li>${t}</li>`).join("");
  }

  // Show spectrum header
  const specHeader = $("spectrum-header");
  if (specHeader && total > 0) specHeader.style.display = "";

  // Spectrum
  const spec = $("spectrum");
  if (spec && total > 0) {
    const countUp = (el, val) => {
      if (!el) return;
      if (el.textContent === String(val)) return;
      el.textContent = fmt(val);
      el.classList.add("pop");
      setTimeout(() => el.classList.remove("pop"), 300);
    };
    
    countUp($("zone-count-safe"), ts);
    countUp($("zone-count-target"), tt);
    countUp($("zone-count-reach"), tr);
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
  const body = $("results-body");
  if (!body) return;

  body.innerHTML = SEC_ORDER.map(cat => {
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
          <button class="btn btn--ghost btn--sm rsection__toggle-btn"
                  aria-expanded="true"
                  onclick="collapseSection('${cat}', this)">
            <span class="rsection__toggle-text">Collapse</span>
            <svg class="chevron" width="10" height="10" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </div>
        <div class="rsection__collapse" id="collapse-${cat.toLowerCase()}">
          <div class="rsection__collapse-inner">
            ${content}
          </div>
        </div>
      </section>`;
  }).join("");
}

window.collapseSection = function(cat, btn) {
  const col = $(`collapse-${cat.toLowerCase()}`);
  if (!col) return;
  const open = btn.getAttribute("aria-expanded") === "true";
  btn.setAttribute("aria-expanded", open ? "false" : "true");
  col.classList.toggle("is-collapsed", open);
  const t = btn.querySelector(".rsection__toggle-text");
  if (t) t.textContent = open ? "Expand" : "Collapse";
};

// ── CARD ──────────────────────────────────────────────────────
function makeCard(rec, idx) {
  const catL  = rec.category === "Reach" ? "reach" : rec.category.toLowerCase();
  const catDisplay = rec.category === "Reach" ? "DREAM" : rec.category.toUpperCase();
  const delay = Math.min(idx * 40, 400);
  const rank  = state.rank;
  const cut   = Math.round(rec.cutoff_rank);

  // ── Rank bar: single cutoff model (no fabricated opening rank) ──
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

  // ── Verdict sentence (matches JEE tone) ──
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

  const isBookmarked = false;
  const bookmarkHtml = `
    <button type="button" class="ccard__bookmark ${isBookmarked ? "is-selected" : ""}"
            aria-label="Add to preference list">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="bookmark-icon">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
      </svg>
    </button>`;

  return `
    <article class="ccard ccard--${catL}" style="animation-delay:${delay}ms">
      ${bookmarkHtml}
      <div class="ccard__meta">
        <span class="tag tag--private">PRIVATE</span>
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
        <span>${esc(rec.quota)} seat</span><span>via COMEDK 2025</span><span>Official cutoff</span>
      </div>
    </article>`;
}

// ── META ──────────────────────────────────────────────────────
async function loadMeta() {
  try {
    const meta = await apiRequest("/api/comedk/meta");
    const note = $("data-note");
    if (note) note.textContent = `COMEDK 2025 · ${fmt(meta.total_programs)} programs`;
    buildGoalGrid();
    // Build panel goal select
    const sel = $("panel-goal");
    if (sel) {
      sel.innerHTML = GOALS.map(g => `<option value="${g.id}">${esc(g.name)}</option>`).join("");
      sel.value = state.goal;
    }
  } catch (e) {
    console.error("Meta load failed:", e?.message);
    // Still build goal grid with static data
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
  fmtRankInput($("comedk-rank"));
  $("comedk-rank")?.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); validateAndNext0(); }
  });
  $("next-0")?.addEventListener("click", validateAndNext0);
  $("back-0")?.addEventListener("click", () => showView("welcome"));

  // Step 1: quota
  bindQuotaRow("quota-row");
  $("next-1")?.addEventListener("click", () => goToStep(2));
  $("back-1")?.addEventListener("click", () => goToStep(0));

  // Step 2: goal (auto-advances on selection, see buildGoalGrid)
  $("back-2")?.addEventListener("click", () => goToStep(1));

  // Step 3: review / confirm
  $("back-3")?.addEventListener("click", () => goToStep(2));
  $("see-colleges-btn")?.addEventListener("click", submitProfile);

  // Review rows → jump back to specific step
  $("rv-rank") ?.addEventListener("click",  () => goToStep(0));
  $("rv-quota")?.addEventListener("click",  () => goToStep(1));
  $("rv-goal") ?.addEventListener("click",  () => goToStep(2));
  $("rv-rank") ?.addEventListener("keydown", e => { if (e.key === "Enter") goToStep(0); });
  $("rv-quota")?.addEventListener("keydown", e => { if (e.key === "Enter") goToStep(1); });
  $("rv-goal") ?.addEventListener("keydown", e => { if (e.key === "Enter") goToStep(2); });

  // Error page
  $("retry-btn")    ?.addEventListener("click", submitProfile);
  $("error-edit-btn")?.addEventListener("click", () => goToStep(0));

  // Panel
  fmtRankInput($("panel-rank"));
  $("panel-rank")?.addEventListener("input", schedulePanelUpdate);
  bindQuotaRow("panel-quota-row", schedulePanelUpdate);
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
  $("filter-search")?.addEventListener("input", e => {
    state.filterText = e.target.value;
    if (state.lastData) renderResults(state.lastData, { keepFilter: true });
  });

  // Spectrum → scroll to section
  $("spectrum")?.addEventListener("click", e => {
    const zone = e.target.closest(".zone");
    if (!zone) return;
    $(`section-${zone.dataset.zone}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  // Share
  $("share-btn")?.addEventListener("click", () => {
    const goalName = GOALS.find(g => g.id === state.goal)?.name || state.goal;
    const msg = `My COMEDK rank ${fmt(state.rank)} (${state.quota}). Check out Disha for free college predictions → ${location.href}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(msg)}`, "_blank", "noopener");
  });

  // Copy link
  $("copy-link-btn")?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      const label = $("copy-link-label");
      if (label) { label.textContent = "Copied!"; setTimeout(() => label.textContent = "Copy link", 2000); }
    } catch { /* ignore */ }
  });

  // Print / Save PDF
  $("print-btn")?.addEventListener("click", () => window.print());

  // Collapse / Expand all
  $("collapse-all-btn")?.addEventListener("click", (e) => {
    const btn = e.target;
    const isExpanded = btn.textContent === "Collapse all";
    
    document.querySelectorAll(".rsection__toggle-btn").forEach(toggleBtn => {
      const match = toggleBtn.getAttribute("onclick")?.match(/'([^']+)'/);
      if (!match) return;
      const cat = match[1];
      const col = $(`collapse-${cat.toLowerCase()}`);
      if (!col) return;
      
      col.hidden = isExpanded;
      toggleBtn.setAttribute("aria-expanded", !isExpanded);
      const textNode = toggleBtn.querySelector(".rsection__toggle-text");
      if (textNode) textNode.textContent = isExpanded ? "Expand" : "Collapse";
    });
    
    btn.textContent = isExpanded ? "Expand all" : "Collapse all";
  });

  // Edit profile — scroll to panel
  $("edit-profile-btn")?.addEventListener("click", () => {
    const panel = $("panel-body");
    const toggle = $("panel-toggle");
    if (panel && toggle) {
      toggle.setAttribute("aria-expanded", "true");
      panel.classList.add("is-open");
      $("panel-rank")?.focus();
    }
  });
}

function validateAndNext0() {
  const rank = parseRank($("comedk-rank"));
  const err  = $("error-rank");
  if (!rank) {
    if (err) { err.textContent = "Please enter a valid COMEDK rank."; err.hidden = false; }
    $("comedk-rank")?.focus();
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
  loadMeta();       // async — also rebuilds goal grid with live data
  showView("welcome");
});
