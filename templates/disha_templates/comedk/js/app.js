"use strict";

/* ═══════════════════════════════════════════════════════════════
   Disha — COMEDK  (standalone SPA, NO shared JEE code)

   View IDs (each step is its own <section>):
     view-welcome  view-step-0  view-step-1  view-step-2  view-step-3
     view-loading  view-results  view-error

   API:  GET  /api/comedk/meta
         POST /api/comedk/recommend
   ═══════════════════════════════════════════════════════════════ */

// ── BRANCHES (loaded from /meta, fallback hardcoded) ──────────
let BRANCHES = [
  { value: "cse",        label: "Computer Science & Engineering" },
  { value: "ai_ds",      label: "AI / Data Science / ML" },
  { value: "cyber",      label: "Cyber Security / Blockchain / IoT" },
  { value: "it",         label: "Information Science / IT" },
  { value: "ece",        label: "Electronics & Communication" },
  { value: "vlsi",       label: "VLSI" },
  { value: "eee",        label: "Electrical & Electronics" },
  { value: "robotics",   label: "Robotics & Automation" },
  { value: "mechanical", label: "Mechanical Engineering" },
  { value: "automobile", label: "Automobile Engineering" },
  { value: "civil",      label: "Civil Engineering" },
  { value: "chemical",   label: "Chemical Engineering" },
  { value: "aerospace",  label: "Aerospace / Aeronautical" },
  { value: "biotech",    label: "Biotechnology" },
  { value: "biomedical", label: "Bio-Medical Engineering" },
  { value: "industrial", label: "Industrial Engineering" },
  { value: "design",     label: "Design" },
  { value: "agriculture",label: "Agricultural Engineering" },
];

// ── ALL VIEW IDs ───────────────────────────────────────────────
const ALL_VIEWS = [
  "welcome", "step-0", "step-1", "step-2", "step-3",
  "loading", "results", "error",
];

// ── STATE ─────────────────────────────────────────────────────
const state = {
  rank:             null,
  quota:            "GM",
  selectedBranches: [],   // list of branch family values, e.g. ["cse", "ai_ds"]
  lastData:         null,
  filterText:       "",
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

// ── BRANCH GRID (multi-select chips) ──────────────────────────
function buildBranchGrid() {
  const grid = $("branch-grid");
  if (!grid) return;
  grid.innerHTML = "";
  for (const b of BRANCHES) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "branch-chip" + (state.selectedBranches.includes(b.value) ? " is-selected" : "");
    chip.dataset.branch = b.value;
    chip.setAttribute("role", "checkbox");
    chip.setAttribute("aria-checked", state.selectedBranches.includes(b.value) ? "true" : "false");
    chip.innerHTML = `
      <svg class="branch-chip__check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
      <span>${esc(b.label)}</span>`;
    chip.addEventListener("click", () => {
      const idx = state.selectedBranches.indexOf(b.value);
      if (idx >= 0) {
        state.selectedBranches.splice(idx, 1);
      } else {
        state.selectedBranches.push(b.value);
      }
      const on = state.selectedBranches.includes(b.value);
      chip.classList.toggle("is-selected", on);
      chip.setAttribute("aria-checked", on ? "true" : "false");
      syncPanelBranches();
    });
    grid.appendChild(chip);
  }
}

// ── PANEL BRANCH CHIPS (sidebar) ──────────────────────────────
function buildPanelBranchChips() {
  const container = $("panel-branch-chips");
  if (!container) return;
  container.innerHTML = "";
  for (const b of BRANCHES) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "panel-branch-chip" + (state.selectedBranches.includes(b.value) ? " is-selected" : "");
    chip.dataset.branch = b.value;
    chip.textContent = b.label;
    chip.addEventListener("click", () => {
      const idx = state.selectedBranches.indexOf(b.value);
      if (idx >= 0) {
        state.selectedBranches.splice(idx, 1);
      } else {
        state.selectedBranches.push(b.value);
      }
      syncPanelBranches();
      syncBranchGrid();
      schedulePanelUpdate();
    });
    container.appendChild(chip);
  }
}

function syncPanelBranches() {
  const container = $("panel-branch-chips");
  if (!container) return;
  container.querySelectorAll(".panel-branch-chip").forEach(chip => {
    const on = state.selectedBranches.includes(chip.dataset.branch);
    chip.classList.toggle("is-selected", on);
  });
}

function syncBranchGrid() {
  const grid = $("branch-grid");
  if (!grid) return;
  grid.querySelectorAll(".branch-chip").forEach(chip => {
    const on = state.selectedBranches.includes(chip.dataset.branch);
    chip.classList.toggle("is-selected", on);
    chip.setAttribute("aria-checked", on ? "true" : "false");
  });
}

// ── Helper: get display text for selected branches ────────────
function selectedBranchesText() {
  if (state.selectedBranches.length === 0) return "All branches";
  return state.selectedBranches
    .map(v => BRANCHES.find(b => b.value === v)?.label || v)
    .join(", ");
}

// ── REVIEW (STEP 3) ───────────────────────────────────────────
function populateReview() {
  const rv = $("rv-rank-val");
  const qv = $("rv-quota-val");
  const bv = $("rv-branch-val");
  if (rv) rv.textContent = state.rank ? fmt(state.rank) : "—";
  if (qv) qv.textContent = state.quota === "GM" ? "GM — General Merit" : "KKR — Kalyana Karnataka";
  if (bv) bv.textContent = selectedBranchesText();
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
        rank:            state.rank,
        quota:           state.quota,
        branch_families: state.selectedBranches,
        bucket:          "all",
        page:            1,
        page_size:       150,
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
  state.rank = r;
  try {
    const data = await apiRequest("/api/comedk/recommend", {
      method: "POST",
      body: JSON.stringify({
        rank:            state.rank,
        quota:           state.quota,
        branch_families: state.selectedBranches,
        bucket:          "all",
        page:            1,
        page_size:       150,
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
  syncPanelBranches();
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
    const branchText = state.selectedBranches.length > 0
      ? state.selectedBranches.length + " branch" + (state.selectedBranches.length > 1 ? "es" : "")
      : "All branches";
    chips.innerHTML = [
      `Rank <strong>${fmt(state.rank)}</strong>`,
      esc(state.quota),
      esc(branchText),
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

  // Rich guidance paragraph
  if (gd) {
    if (total > 0) {
      const branchNote = state.selectedBranches.length > 0
        ? `Filtered to ${state.selectedBranches.length} preferred branch${state.selectedBranches.length > 1 ? "es" : ""}.`
        : "Showing all branches.";
      gd.textContent = `Found ${fmt(total)} eligible college–program options for your profile (showing ${fmt(total)}). They are grouped into Target, Dream and Safe. ${branchNote}`;
    } else {
      gd.textContent = "Try adjusting your rank, quota, or branch preferences to find matching programs.";
    }
  }

  // Tips list
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
  if (specHeader) {
    specHeader.style.display = total > 0 ? "" : "none";
  }

  // Spectrum
  const spec = $("spectrum");
  if (spec) {
    spec.style.display = total > 0 ? "" : "none";
    if (total > 0) {
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

  // ── Verdict sentence ──
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
    // Update BRANCHES from server if available
    if (meta.branch_families && meta.branch_families.length > 0) {
      BRANCHES = meta.branch_families;
    }
    buildBranchGrid();
    buildPanelBranchChips();
  } catch (e) {
    console.error("Meta load failed:", e?.message);
    // Still build branch grid with static data
    buildBranchGrid();
    buildPanelBranchChips();
  }
}

// ── EVENTS ────────────────────────────────────────────────────
function bindEvents() {
  // Welcome → step 0
  $("begin-btn")?.addEventListener("click", () => goToStep(0));

  // Restart
  $("restart-btn")?.addEventListener("click", () => {
    state.rank = null; state.quota = "GM"; state.selectedBranches = [];
    syncQuota();
    syncBranchGrid();
    syncPanelBranches();
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

  // Step 2: branch preference (Continue button advances to step 3)
  $("next-2")?.addEventListener("click", () => goToStep(3));
  $("back-2")?.addEventListener("click", () => goToStep(1));

  // Step 3: review / confirm
  $("back-3")?.addEventListener("click", () => goToStep(2));
  $("see-colleges-btn")?.addEventListener("click", submitProfile);

  // Review rows → jump back to specific step
  $("rv-rank")  ?.addEventListener("click",  () => goToStep(0));
  $("rv-quota") ?.addEventListener("click",  () => goToStep(1));
  $("rv-branch")?.addEventListener("click",  () => goToStep(2));
  $("rv-rank")  ?.addEventListener("keydown", e => { if (e.key === "Enter") goToStep(0); });
  $("rv-quota") ?.addEventListener("keydown", e => { if (e.key === "Enter") goToStep(1); });
  $("rv-branch")?.addEventListener("keydown", e => { if (e.key === "Enter") goToStep(2); });

  // Error page
  $("retry-btn")    ?.addEventListener("click", submitProfile);
  $("error-edit-btn")?.addEventListener("click", () => goToStep(0));

  // Panel
  fmtRankInput($("panel-rank"));
  $("panel-rank")?.addEventListener("input", schedulePanelUpdate);
  bindQuotaRow("panel-quota-row", schedulePanelUpdate);

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
  buildBranchGrid();
  buildPanelBranchChips();
  bindEvents();
  loadMeta();       // async — also rebuilds branch grid with live data
  showView("welcome");
});
