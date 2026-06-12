"use strict";

/* ════════════════════════════════════════════════════════════════════════
   Disha — app logic
   Views: welcome → guided 5-step flow → loading → results (or error).
   Talks to the FastAPI backend via fetchMeta() / fetchRecommendations()
   defined in api.js.
   ════════════════════════════════════════════════════════════════════════ */

// ── Static content ──────────────────────────────────────────────────────

const GOALS = [
  {
    id: "coding",
    name: "Coding & software",
    desc: "Build things, aim for SDE roles",
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  },
  {
    id: "research",
    name: "Research & higher studies",
    desc: "MS, MTech or PhD pathways",
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg>',
  },
  {
    id: "mba",
    name: "MBA & management",
    desc: "Brand, network, placements",
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>',
  },
  {
    id: "core",
    name: "Core engineering",
    desc: "Practice the discipline you study",
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
  },
  {
    id: "undecided",
    name: "Not sure yet",
    desc: "Keep as many doors open as possible",
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  },
];

// Counsellor tips per goal, shown under the API's interest guidance.
const GOAL_TIPS = {
  coding: [
    "CSE at the top NITs often closes earlier than non-CS branches at newer IITs — compare both before ranking choices.",
    "ECE and Mathematics & Computing are close substitutes for CSE in software placements.",
    "Consistent DSA practice and internships outweigh a one-tier branch difference.",
  ],
  research: [
    "Prefer institutes with active research groups in your area — check faculty pages, not just rankings.",
    "IISc and IISERs are strong alternatives if pure science appeals to you.",
    "Start approaching professors for small projects in your first year.",
  ],
  mba: [
    "An older IIT or NIT brand carries real weight in CAT shortlists and placements.",
    "Branch choice is secondary — pick one you can score well in.",
    "Use clubs, fests and POR roles to build the profile MBA programs look for.",
  ],
  core: [
    "Older NITs frequently have stronger core-company relationships than newer IITs.",
    "PSU recruitment through GATE is a dependable core-sector pathway.",
    "Look for institutes with labs and industry tie-ups in your specific domain.",
  ],
  undecided: [
    "Most IITs allow a branch change after first year based on GPA.",
    "Broad branches (EE, Mechanical, Engineering Physics) keep many doors open.",
    "Talk to seniors in branches you're considering before locking a choice.",
  ],
};

const QUOTA_LABELS = {
  AI: "All-India seat",
  HS: "Home-state quota",
  OS: "Other-state quota",
  GO: "Goa quota",
  JK: "J&K quota",
  LA: "Ladakh quota",
};

const SECTION_META = {
  Target: { title: "Target", sub: "your best-fit zone" },
  Reach:  { title: "Reach",  sub: "worth a try" },
  Safe:   { title: "Safe",   sub: "strong backups" },
};
const SECTION_ORDER = ["Target", "Reach", "Safe"];

const LOADING_LINES = [
  "Reading last year's cutoffs…",
  "Matching programs to your profile…",
  "Sorting Safe, Target and Reach…",
];

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

// ── App state ───────────────────────────────────────────────────────────

const state = {
  meta: null,
  step: 0,
  gender: "male",
  goal: null,
  lastPayload: null,
  lastData: null,
  filterText: "",
  filterType: "",
};

const TOTAL_STEPS = 5;

// ── View switching ──────────────────────────────────────────────────────

const VIEWS = ["welcome", "flow", "loading", "results", "error"];

function showView(name) {
  for (const v of VIEWS) {
    $(`view-${v}`).classList.toggle("is-active", v === name);
  }
  $("restart-btn").hidden = name === "welcome";
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
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
  });
}

// ── Guided flow ─────────────────────────────────────────────────────────

const STEP_BUTTON_LABELS = ["Continue", "Continue", "Continue", "Continue", "Show my colleges"];

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
  $("flow-next").textContent = STEP_BUTTON_LABELS[index];

  if (index === 4) renderReview();

  const firstInput = document.querySelector(
    `.step[data-step="${index}"] input, .step[data-step="${index}"] select`
  );
  if (firstInput && window.matchMedia("(min-width: 720px)").matches) firstInput.focus();
}

function validateStep(index) {
  if (index === 0) {
    const mains = parseRankInput($("mains-rank"));
    const adv = parseRankInput($("adv-rank"));
    const err = $("error-ranks");
    if (mains === null && adv === null) {
      err.textContent = "Enter at least one rank — JEE Main or Advanced — to continue.";
      err.hidden = false;
      return false;
    }
    err.hidden = true;
    return true;
  }
  if (index === 2) {
    const err = $("error-state");
    if (!$("home-state").value) {
      err.textContent = "Pick your home state — it changes which NIT seats you can claim.";
      err.hidden = false;
      return false;
    }
    err.hidden = true;
    return true;
  }
  if (index === 3) {
    const err = $("error-goal");
    if (!state.goal) {
      err.textContent = "Pick one — \u201cNot sure yet\u201d counts.";
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

// gender pills
function bindGenderRow() {
  const row = $("gender-row");
  row.addEventListener("click", (e) => {
    const btn = e.target.closest(".choice");
    if (!btn) return;
    state.gender = btn.dataset.value;
    row.querySelectorAll(".choice").forEach((c) => {
      const on = c === btn;
      c.classList.toggle("is-selected", on);
      c.setAttribute("aria-checked", on ? "true" : "false");
    });
    const note = $("gender-note");
    if (state.gender === "female") {
      note.textContent = "Female-only (supernumerary) seats will be included for you — they often close at better ranks.";
    } else if (state.gender === "other") {
      note.textContent = "You'll be matched against gender-neutral seat pools.";
    } else {
      note.innerHTML = "&nbsp;";
    }
  });
}

// goal cards
function buildGoalCards() {
  const grid = $("goal-grid");
  grid.innerHTML = "";
  for (const goal of GOALS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "goal-card";
    btn.dataset.goal = goal.id;
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", "false");
    btn.innerHTML = `
      <span class="goal-card__icon" aria-hidden="true">${goal.icon}</span>
      <span>
        <span class="goal-card__name">${escapeHtml(goal.name)}</span>
        <span class="goal-card__desc">${escapeHtml(goal.desc)}</span>
      </span>`;
    btn.addEventListener("click", () => {
      state.goal = goal;
      grid.querySelectorAll(".goal-card").forEach((c) => {
        const on = c === btn;
        c.classList.toggle("is-selected", on);
        c.setAttribute("aria-checked", on ? "true" : "false");
      });
      $("error-goal").hidden = true;
      // small pause so the selection registers visually, then advance
      setTimeout(() => { if (state.step === 3) advanceStep(); }, prefersReducedMotion ? 0 : 260);
    });
    grid.appendChild(btn);
  }
}

// review
function categoryLabel() {
  const sel = $("seat-category");
  return sel.options[sel.selectedIndex]?.text.replace(/ — coming soon$/, "") || "General";
}

function renderReview() {
  const mains = parseRankInput($("mains-rank"));
  const adv = parseRankInput($("adv-rank"));
  const genderText = { male: "Male", female: "Female", other: "Other" }[state.gender];

  const rows = [
    { key: "JEE Main rank", val: mains ? fmt(mains) : "<small>not given</small>", step: 0 },
    { key: "JEE Advanced rank", val: adv ? fmt(adv) : "<small>not given</small>", step: 0 },
    { key: "Gender", val: escapeHtml(genderText), step: 1 },
    { key: "Category", val: escapeHtml(categoryLabel()), step: 1 },
    { key: "Home state", val: escapeHtml($("home-state").value || "—"), step: 2 },
    { key: "Goal", val: escapeHtml(state.goal ? state.goal.name : "—"), step: 3 },
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
    stateSel.innerHTML = '<option value="" disabled selected>Choose your state…</option>';
    for (const s of meta.states) {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      stateSel.appendChild(opt);
    }

    const catSel = $("seat-category");
    catSel.innerHTML = "";
    const cats = meta.categories?.length
      ? meta.categories
      : [{ value: "OPEN", label: "General", available: true }];
    for (const c of cats) {
      const opt = document.createElement("option");
      opt.value = c.value;
      const label = String(c.label || c.value)
        .replace(/OPEN \(General \/ CRL\)/i, "General (OPEN)")
        .replace(/^OPEN$/i, "General (OPEN)");
      opt.textContent = c.available ? label : `${label} — coming soon`;
      opt.disabled = !c.available;
      catSel.appendChild(opt);
    }
    catSel.value = "OPEN";
    $("category-note").textContent =
      "Cutoff data currently covers OPEN (CRL) seats; reserved-category cutoffs are on the way.";

    $("begin-btn").disabled = false;
  } catch {
    $("meta-offline").hidden = false;
  }
}

// ── Submission ──────────────────────────────────────────────────────────

let loadingTimer = null;
let requestSeq = 0;

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
  const mains = parseRankInput($("mains-rank"));
  const adv = parseRankInput($("adv-rank"));
  const payload = {
    gender: state.gender === "female" ? "female" : "male",
    home_state: $("home-state").value,
    goal: state.goal.id,
    seat_category: $("seat-category").value || "OPEN",
    max_results: 150,
  };
  if (mains !== null) payload.mains_rank = mains;
  if (adv !== null) payload.adv_rank = adv;
  return payload;
}

async function submitProfile() {
  state.lastPayload = buildPayload();
  await runRequest(state.lastPayload);
}

async function runRequest(payload) {
  const seq = ++requestSeq;
  showView("loading");
  startLoadingLines();
  const minDelay = new Promise((r) => setTimeout(r, prefersReducedMotion ? 0 : 1100));

  try {
    const [data] = await Promise.all([fetchRecommendations(payload), minDelay]);
    if (seq !== requestSeq) return;
    stopLoadingLines();
    state.lastData = data;
    renderResults(data);
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
  if (p.mains_rank) chips.push(`Main <strong>${fmt(p.mains_rank)}</strong>`);
  if (p.adv_rank) chips.push(`Advanced <strong>${fmt(p.adv_rank)}</strong>`);
  chips.push(escapeHtml(p.home_state));
  chips.push(escapeHtml(categoryLabel()));
  if (state.goal) chips.push(escapeHtml(state.goal.name));

  $("profile-chips").innerHTML = chips
    .map((c) => `<span class="pchip">${c}</span>`)
    .join("");
}

function noteHeadline(byCat, total) {
  if (total === 0) return "Let's adjust the compass.";
  if ((byCat.Target || 0) > 0 && (byCat.Safe || 0) > 0) return "You're standing in a good spot.";
  if ((byCat.Target || 0) > 0) return "You have real options on the table.";
  if ((byCat.Safe || 0) > 0) return "You have solid ground to build from.";
  return "It's a stretch — but not out of reach.";
}

function renderNote(data) {
  const byCat = data.counts?.by_category || {};
  const total = data.counts?.total ?? 0;

  $("note-headline").textContent = noteHeadline(byCat, total);

  const pieces = [];
  if (data.interest_guidance) pieces.push(data.interest_guidance);
  if (data.guidance) pieces.push(data.guidance);
  $("note-guidance").textContent = pieces.join(" ");

  const tips = GOAL_TIPS[state.goal?.id] || [];
  $("note-tips").innerHTML = tips
    .map((t) => `<li>${escapeHtml(t)}</li>`)
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
    verdict = `You: ${fmt(rank)} — ahead of last year's opening rank.`;
  } else if (rec.category === "Target") {
    const through = Math.round(((rank - open) / span) * 100);
    verdict =
      through <= 55
        ? `You: ${fmt(rank)} — comfortably inside last year's window.`
        : `You: ${fmt(rank)} — inside the window, closer to the edge.`;
  } else {
    const past = Math.max(1, Math.round(((rank - close) / close) * 100));
    verdict = `You: ${fmt(rank)} — about ${past}% past last year's closing. Cutoffs shift.`;
  }

  return `
    <div class="rankbar">
      <div class="rankbar__track">
        <div class="rankbar__window" style="left:${winLeft.toFixed(1)}%;right:${(100 - winRight).toFixed(1)}%"></div>
        <div class="rankbar__you" style="left:${youPos.toFixed(1)}%" title="Your rank: ${fmt(rank)}"></div>
      </div>
      <div class="rankbar__labels">
        <span>opens <strong>${fmt(open)}</strong></span>
        <span>closes <strong>${fmt(close)}</strong></span>
      </div>
      <p class="rankbar__verdict">${escapeHtml(verdict)}</p>
    </div>`;
}

function cardHtml(rec, index) {
  const cat = rec.category.toLowerCase();
  const typeClass = `tag--${rec.institute_type.toLowerCase()}`;
  const delay = prefersReducedMotion ? 0 : Math.min(index * 45, 420);
  const star = rec.matched_interest
    ? `<span class="ccard__star" title="Strong fit for your stated goal">
         <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8L12 2z"/></svg>
         fits your goal</span>`
    : "";

  const degreeNote = /dual/i.test(rec.degree) ? "Dual degree (5 yr)" : "";
  const poolNote = rec.gender_pool === "female" ? "Female-only seat" : "";
  const foot = [
    QUOTA_LABELS[rec.quota] || rec.quota,
    rec.exam === "advanced" ? "via JEE Advanced" : "via JEE Main",
    degreeNote,
    poolNote,
  ].filter(Boolean);

  return `
    <article class="ccard ccard--${cat}" style="animation-delay:${delay}ms">
      <div class="ccard__meta">
        <span class="tag ${typeClass}">${escapeHtml(rec.institute_type)}</span>
        <span class="tag">${escapeHtml(rec.institute_state)}</span>
        ${star}
      </div>
      <h3 class="ccard__institute">${escapeHtml(rec.institute)}</h3>
      <p class="ccard__branch">${escapeHtml(rec.branch)}</p>
      ${rankBarHtml(rec)}
      <div class="ccard__foot">${foot.map((f) => `<span>${escapeHtml(f)}</span>`).join("")}</div>
    </article>`;
}

function recPassesFilters(rec) {
  if (state.filterType && rec.institute_type !== state.filterType) return false;
  if (!state.filterText) return true;
  const q = state.filterText;
  return (
    rec.institute.toLowerCase().includes(q) ||
    rec.branch.toLowerCase().includes(q) ||
    rec.branch_full.toLowerCase().includes(q) ||
    rec.institute_state.toLowerCase().includes(q)
  );
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

    const meta = SECTION_META[catName];
    const section = document.createElement("section");
    section.className = "rsection";
    section.id = `section-${catName.toLowerCase()}`;
    section.innerHTML = `
      <div class="rsection__head">
        <h2 class="rsection__title">
          <span class="dot dot--${catName.toLowerCase()}" aria-hidden="true"></span>
          ${meta.title} <span class="rsection__count">· ${meta.sub} · ${visible.length}</span>
        </h2>
      </div>
      ${blurbs[catName] ? `<p class="rsection__blurb">${escapeHtml(blurbs[catName])}</p>` : ""}
      <div class="cards">${visible.map((r, i) => cardHtml(r, i)).join("")}</div>`;
    container.appendChild(section);
  }

  const hasResults = recs.length > 0;
  $("empty-results").hidden = hasResults;
  $("empty-filtered").hidden = !hasResults || anyShown;
  $("toolbar").style.display = hasResults ? "" : "none";
  $("spectrum").style.display = hasResults ? "" : "none";
}

function renderResults(data) {
  state.filterText = "";
  state.filterType = "";
  $("filter-search").value = "";
  document.querySelectorAll("#type-chips .chip").forEach((c) =>
    c.classList.toggle("is-active", c.dataset.type === "")
  );

  renderProfileChips();
  renderNote(data);

  const byCat = data.counts?.by_category || {};
  countUp($("zone-count-safe"), byCat.Safe || 0);
  countUp($("zone-count-target"), byCat.Target || 0);
  countUp($("zone-count-reach"), byCat.Reach || 0);
  document.querySelectorAll(".zone").forEach((z) => {
    z.classList.toggle("is-empty", !(byCat[z.dataset.zone] > 0));
  });

  renderSections();
}

// ── Events ──────────────────────────────────────────────────────────────

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

  $("restart-btn").addEventListener("click", () => showView("welcome"));
  $("wordmark").addEventListener("click", (e) => {
    e.preventDefault();
    showView("welcome");
  });

  $("retry-btn").addEventListener("click", () => {
    if (state.lastPayload) runRequest(state.lastPayload);
  });

  const backToReview = () => {
    showView("flow");
    goToStep(4, { backwards: true });
  };
  $("error-edit-btn").addEventListener("click", backToReview);
  $("edit-profile-btn").addEventListener("click", backToReview);
  $("empty-edit-btn").addEventListener("click", backToReview);

  $("filter-search").addEventListener("input", (e) => {
    state.filterText = e.target.value.trim().toLowerCase();
    renderSections();
  });

  $("type-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    state.filterType = chip.dataset.type;
    document.querySelectorAll("#type-chips .chip").forEach((c) =>
      c.classList.toggle("is-active", c === chip)
    );
    renderSections();
  });

  $("clear-filters-btn").addEventListener("click", () => {
    state.filterText = "";
    state.filterType = "";
    $("filter-search").value = "";
    document.querySelectorAll("#type-chips .chip").forEach((c) =>
      c.classList.toggle("is-active", c.dataset.type === "")
    );
    renderSections();
  });

  $("spectrum").addEventListener("click", (e) => {
    const zone = e.target.closest(".zone");
    if (!zone) return;
    const target = $(`section-${zone.dataset.zone.toLowerCase()}`);
    if (target) target.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "start" });
  });
}

// ── Init ────────────────────────────────────────────────────────────────

attachRankFormatting($("mains-rank"));
attachRankFormatting($("adv-rank"));
bindGenderRow();
buildGoalCards();
bindEvents();
showView("welcome");
loadMeta();
