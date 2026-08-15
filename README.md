<!--
  Note for contributors AND for AI coding agents (Antigravity, Claude Code, etc.)
  working on this repo:

  This README, docs/API.md, CONTRIBUTING.md, and templates/disha_templates/README.md
  are the ONLY source of truth for how this project works — they replace a set of
  docs that had drifted badly out of date. Any task that touches a backend endpoint
  or response field, adds/changes an exam, changes setup/run steps, or changes the
  frontend file structure MUST update the relevant doc(s) in the SAME change, not as
  a follow-up. See CONTRIBUTING.md for the full policy and a "docs checklist" of
  trigger questions to run through before you consider a change finished.
-->

# Disha (दिशा) — Multi-Exam College Recommender & Analytics Portal

Disha helps engineering aspirants in India turn a rank into a shortlist of realistic colleges and branches. A student enters their rank (and, for JEE, gender/home-state/category/career-goal), and Disha returns institute+branch options grouped into **Safe / Target / Reach ("Dream")** buckets, each with an estimated admission probability and a plain-language reason, computed from official cutoff data.

**Live deployment:** [jee-college-finder-utmt-asov.onrender.com](https://jee-college-finder-utmt-asov.onrender.com/) (Render free tier — the instance sleeps when idle, so the first load after a while can take ~30s to wake up).

![Disha Portal — Desktop and Mobile View](./screenshots/hero.png)

### Exams supported today

| Exam | Status | Cutoff data | Notes |
|---|---|---|---|
| **JEE** (Main + Advanced, via JoSAA) | ✅ Original, most complete implementation | 2025, round-wise (`Opening_R1…R6`/`Closing_R1…R6`) | The reference implementation every other exam is patterned on. |
| **COMEDK** | ✅ Complete, recently finished | 2025, single closing rank per programme/quota | Built by structurally porting JEE's frontend/backend patterns and adapting them to COMEDK's single-cutoff data — see [Architecture](#architecture-overview) below. |
| **KCET** | ✅ Complete | 2025, round 1 only | Rebuilt to JEE-architecture parity. An earlier README claimed `POST /api/kcet/recommend` returned HTTP 500 on every call; that was fixed and is now pinned by 70 golden cases, all returning 200. |

This table, and everything below it, was written by reading the current code — not by trusting the previous README, which had drifted (wrong HTTP methods, wrong margin constants, a `Data/` folder that no longer exists, and no mention of COMEDK or KCET at all). If you find something here that no longer matches the code, that's a docs bug — fix it in the same change that changed the behavior.

---

## Docs checklist

Before you consider any change to this repo finished, ask:

- [ ] **Did I add/change an API endpoint or a response/request field?** → update [docs/API.md](docs/API.md) and, if it changes the high-level picture, the tables above.
- [ ] **Did I add a new exam, or change how an existing exam's frontend/backend is structured?** → update [Architecture overview](#architecture-overview), [Directory layout](#directory-layout), and [Adding a new exam](#adding-a-new-exam) below.
- [ ] **Did I change setup/install/run steps, dependencies, or env vars?** → update [Setup](#setup) below.
- [ ] **Did I touch `templates/disha_templates/`?** → update [templates/disha_templates/README.md](templates/disha_templates/README.md) too; it's a separate file and does not auto-sync with this one.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full policy this checklist is a summary of.

---

## Setup

### Prerequisites

- **Python 3.9+** (the committed `venv/` in this checkout was built with 3.9; `run.bat`'s own error message asks for 3.12+ — either works against the pinned dependencies, but prefer 3.12+ for a fresh setup). No Node.js, no frontend build tool, no database — the frontend is static files served directly by FastAPI.
- `pip` for installing Python dependencies.

### Install

```bash
# From the repository root
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` pins: `fastapi`, `uvicorn[standard]`, `pandas`, `openpyxl`, `pydantic`, `aiofiles`, `pytest`, `httpx`. Note: `openpyxl` and `aiofiles` are currently **not imported anywhere in the app code** (verified by grep) — they're leftovers from an earlier Excel-based data pipeline and possible future use; installing them is harmless, just don't be surprised they're unused today.

### Run the dev server

```bash
uvicorn main:app --reload --port 8000
# or: python main.py   (reads PORT / APP_DEBUG env vars, defaults to port 8000)
```

Open:

| URL | What |
|---|---|
| `http://127.0.0.1:8000/` | Landing page — pick an exam |
| `http://127.0.0.1:8000/exam/jee` | JEE recommender |
| `http://127.0.0.1:8000/exam/comedk` | COMEDK recommender |
| `http://127.0.0.1:8000/exam/kcet` | KCET recommender |
| `http://127.0.0.1:8000/stats` | JEE insights dashboard |
| `http://127.0.0.1:8000/exam/comedk/stats` | COMEDK insights dashboard |
| `http://127.0.0.1:8000/exam/kcet/stats` | KCET insights dashboard |
| `http://127.0.0.1:8000/api/docs` | Swagger UI (auto-generated, live) |
| `http://127.0.0.1:8000/api/redoc` | ReDoc |

On Windows, double-clicking `run.bat` does the `pip install` + `python main.py` steps for you.

**No env vars or config files are required to run locally.** All configuration (CORS, data-file paths, tuning constants) lives in `app/disha/config.py` and `app/disha/comedk/config.py` as hard-coded class attributes, by design (see the docstring at the top of `app/disha/config.py`). One env var exception exists but is dev-only and optional: `PORT` and `APP_DEBUG`, read only inside `main.py`'s `if __name__ == "__main__":` block (i.e. only when you run `python main.py` directly, not `uvicorn main:app`).

> **Verified inconsistency:** `render.yaml` sets a `CORS_ORIGINS` env var for the deployed service, but `app/disha/config.py`'s `Settings.cors_origins` is a hard-coded `"*"` — nothing in the codebase reads `os.environ["CORS_ORIGINS"]`. That env var currently has no effect. If you wire it up, remove this note.

### Simulating the UTMT portal integration locally

Disha is designed to be plugged into a larger FastAPI portal (see [Architecture](#architecture-overview)). To test that integration path without the real portal:

```bash
uvicorn mock_portal:app --reload --port 8001
```

then visit `http://127.0.0.1:8001/learning_games/` — `mock_portal.py` mounts the exact same router+static-files pattern the real portal is expected to use, under a `/learning_games` prefix, so you can catch prefix-related bugs (relative asset paths, `config.js`'s prefix auto-detection) before handing the code off. `mock_portal.py` and this scenario are also documented in [DISHA_INTEGRATION_QA.md](DISHA_INTEGRATION_QA.md).

### Tests

```bash
pytest tests/ -v
```

Three layers:

- `tests/golden/` — **297 characterization cases across all three exams**, pinning the exact current API responses. Read [tests/golden/README.md](tests/golden/README.md) before changing engine code; this is the safety net that makes consolidation provable. Re-capture with `python -m tests.golden.capture`, and treat the resulting diff as the record of what you changed.
- `tests/test_page_routes.py` — every registered exam's page and stats routes resolve, with the right cache headers. Derived from `registry.EXAMS`, so a new exam is covered automatically.
- `tests/test_api.py`, `tests/test_recommender.py`, `tests/test_enhancements.py` — JEE-specific HTTP and unit tests.

COMEDK and KCET previously had **no automated coverage at all**; the golden suite is their first.

### Build steps

None. The frontend is hand-written HTML/CSS/vanilla JS served as-is; there is no bundler, no `npm install`, no compilation step for either backend or frontend.

---

## Architecture overview

```
                         ┌─────────────────────────────────────────┐
   Browser  ── HTTP ──▶  │  FastAPI app  (main.py, or a host        │
                         │  portal's main.py in production)         │
                         │                                           │
                         │  1. disha_router  (app/disha/routes.py)  │
                         │     ├─ JEE routes            (this file) │
                         │     ├─ comedk_router  (app/disha/comedk) │
                         │     └─ kcet_router    (app/disha/kcet)   │
                         │                                           │
                         │  2. StaticFiles / catch-all               │
                         │     serves templates/disha_templates/**  │
                         └─────────────────────────────────────────┘
                                        │
                                        ▼
                     app/disha/data/*.csv,  comedk/data/*.csv,  kcet/data/*.csv
                     (loaded into memory once, cached with lru_cache/module globals)
```

- **Backend framework:** FastAPI (Python), one process, no database. Each exam's data file is read into memory on first use and cached (`@lru_cache` in JEE's `data_loader.py`; a module-level `_cached_programs` global in COMEDK/KCET's). There is no ORM, no persistence layer, no background jobs — every request runs a synchronous, in-memory filter/sort pass over the cached list.
- **One router, three exams bundled together:** `app/disha/routes.py` defines the JEE endpoints *and* imports+includes `comedk_router` and `kcet_router` into the same `APIRouter` instance (`router.include_router(comedk_router)` / `...(kcet_router)`). So `main.py` (or a host portal) only ever imports **one** router (`app.disha.routes.router`) to get all three exams' API surface at once — see [docs/API.md](docs/API.md) for the full endpoint list this produces.
- **Frontend approach:** no framework, no build step. Each exam is a **separate, independently-maintained vanilla-JS single-page app** — a static HTML shell plus a per-exam `app.js` that manages its own view state and talks to its own backend endpoints via `fetch`. There is a shared HTML+JS **landing page** (`index.html` + `js/landing.js`) that is just a config-driven list of `<a href="exam/...">` cards — clicking one is a real page navigation, not a client-side route change.
- **Wiring between frontend and backend:** the frontend never hardcodes a hostname. `js/config.js` inspects its own `<script src>` URL at load time to figure out what prefix it's mounted under (`""` at root, `"/learning_games"` inside a portal, etc.) and sets `window.APP_CONFIG.API_BASE_URL` accordingly — this is what lets the *same* static files work standalone and inside the UTMT portal without editing anything.

### Mostly-separate implementations, converging on a shared core

The exams began as independent copy-and-adapt forks. That is being unwound
incrementally, and the two layers now have different answers:

**Already shared** (`app/disha/core/`, `app/disha/registry.py`):

- `core/curation.py` — bucket ordering, per-institute capping and top-rank
  detection. Previously implemented once per exam; the three copies were
  character-identical apart from attribute names (`closing_rank` vs
  `cutoff_rank`, `branch` vs `program`), so they are now one implementation
  parameterised by attribute name.
- `registry.py` — the single place an exam is registered. API router mounting
  and page-route generation derive from it.

Nothing in `core/` imports from an exam package. The dependency direction is
strictly one-way, and that is what allows a new exam to be added without
editing shared code.

**Still per-exam, and deliberately so** — these are genuine domain
differences, not duplication:

| Concern | Why it can't be shared |
|---|---|
| Cutoff model | JoSAA publishes an opening–closing *window*; KCET and COMEDK publish a single *point*, so their admitted band has to be modelled. JEE's overqualification prune must **not** be applied to point-cutoff exams — doing so once caused a rank-500 COMEDK student to see 37 programmes instead of 459 (`comedk/recommender.py:36-46`). |
| Tuning constants | Each exam's `config.py` documents percentiles measured from its own dataset. KCET's tail runs ~2.2× COMEDK's. |
| Eligibility axes | JEE has home-state quota and a gender pool; COMEDK has neither (all colleges are in Karnataka); KCET folds region into the category code (`2AG`, `SCK`). |
| Branch classifiers | Three genuinely different strategies. KCET's word-order-agnostic keyword bag exists because its source scrape is corrupted — `"BLO CK CHAIN"`, `"CYB ER SECURITY"`. |
| Brand scoring | JEE hardcodes public prestige tiers; COMEDK derives them from cutoff percentiles; KCET has no signal at all, because no authoritative Karnataka tier list exists. |
| `confidence` | Means different things: JEE's four round-volatility tags vs the point exams' z-score buckets. A shared enum would force one of them to lie. |

The remaining structural facts below still hold for the per-exam layer:

- **Backend:** `app/disha/` (JEE) and `app/disha/comedk/` (COMEDK) each have their own `config.py`, `data_loader.py`, `recommender.py`, `schemas.py`, `states.py`, `stats_loader.py`, and `routes.py`. None of these modules import from the other exam's package. COMEDK's docstrings explicitly say things like *"Mirrors `app/disha/config.py` in structure"* and *"Mirrors `app/disha/schemas.py` in shape"* — it was built by reading JEE's modules and writing COMEDK-shaped equivalents, not by extracting a shared base class or config schema. Where COMEDK's domain genuinely differs (a single published cutoff instead of an opening/closing pair; no home-state axis because all colleges are in Karnataka), its constants and formulas were **re-derived from scratch** — see the long design-rationale comments in `app/disha/comedk/config.py` for why COMEDK's band math can't just reuse JEE's percentages unchanged.
- **Frontend:** `templates/disha_templates/comedk/js/app.js` opens with the comment *"Ported from JEE app.js — structurally identical, domain-adapted."* It reuses the shared `js/config.js` and `js/api.js` (API-base-URL detection and the generic fetch wrapper), but **not** `js/i18n.js` — COMEDK's UI is English-only, with no equivalent i18n layer built. Its own `comedk/js/app.js` was written by copying JEE's `js/app.js` view-state/rendering structure and adapting each section (fewer guided-flow steps, a single-cutoff "rank bar" instead of JEE's opening/closing rank ruler, quota pills instead of a home-state dropdown) rather than sharing code with it.
- **KCET follows the same pattern.** It was rebuilt to JEE-architecture parity and is complete; the "returns 500 on every call" warning in older revisions of this README is out of date.

**The cost that remains.** Backend routing and curation are now fixed in one
place, but the recommendation pipeline itself is still written out once per
exam, and the **frontend is still fully forked**: `kcet/js/app.js` and
`comedk/js/app.js` are ~99% identical after normalising renames, and their
`index.html` files are 94% identical with every difference being a string
swap. A UI fix still has to be applied three times, and that porting is
already failing — see the frozen-bug list in
[tests/golden/README.md](tests/golden/README.md).

**Before changing any of this, read [tests/golden/README.md](tests/golden/README.md).**
297 characterization cases pin the current API responses for all three exams.
They are what makes further consolidation safe, and before they existed KCET
and COMEDK had no automated coverage whatsoever.

---

## Directory layout

```text
.
├── main.py                        # FastAPI app: mounts disha_router + serves templates/disha_templates/ as static files
├── mock_portal.py                 # Simulates the UTMT host portal locally (test-only, see Setup)
├── conftest.py                    # Makes `app...` importable from tests/
├── requirements.txt
├── render.yaml                    # Render.com deploy config (uvicorn main:app)
├── run.bat                        # Windows: pip install + run
├── docs/
│   └── API.md                     # Full per-exam API contract (endpoints, request/response shapes, comparison table)
├── CONTRIBUTING.md                # Docs-stay-in-sync policy + checklist
├── DISHA_INTEGRATION_QA.md        # Q&A on plugging Disha into the UTMT host portal
│
├── app/
│   ├── __init__.py
│   └── disha/
│       ├── registry.py             # THE place an exam is registered — drives router mounting + page routes
│       ├── core/                    # Exam-agnostic engine. Imports nothing from an exam package.
│       │   └── curation.py          # Bucket ordering, per-institute capping, top-rank detection (shared by all 3)
│       ├── routes.py               # JEE API endpoints; delegates all exam wiring to registry.py
│       ├── config.py                # JEE settings (CORS, data paths, data_mode)
│       ├── data_loader.py           # Reads josaa_merged_2025.csv, computes opening/closing ranks + volatility tags
│       ├── recommender.py           # JEE recommendation pipeline (filter → bucket → score → probability → sort)
│       ├── schemas.py               # JEE request/response Pydantic models
│       ├── states.py                # Indian states, institute→state map, branch-tag classifier, career-goal weights
│       ├── stats_loader.py          # Computes /api/stats from the JEE dataset
│       ├── data/
│       │   └── josaa_merged_2025.csv   # JEE 2025 cutoffs — all categories, all 6 JoSAA rounds
│       │
│       ├── comedk/                  # Independent COMEDK implementation (see Architecture)
│       │   ├── routes.py, config.py, data_loader.py, recommender.py, schemas.py, states.py, stats_loader.py
│       │   └── data/comedk_2025.csv    # COMEDK 2025 — single closing rank per programme/quota
│       │
│       └── kcet/                    # Independent KCET implementation (incomplete — see status table)
│           ├── routes.py, schemas.py, data_loader.py, recommender.py, stats_loader.py, config.py
│           └── data/kcet_2025.csv      # KCET 2025 — round 1 only
│
├── templates/disha_templates/       # The entire frontend — see its own README.md for the full breakdown
│   ├── index.html                     # Landing page — exam picker (config-driven cards)
│   ├── jee.html                       # JEE SPA shell
│   ├── stats.html                     # JEE insights dashboard
│   ├── comedk/index.html, comedk/stats.html, comedk/js/app.js
│   ├── kcet/index.html, kcet/stats.html, kcet/js/app.js
│   ├── css/style.css                  # Shared design system used by every exam's HTML
│   ├── js/
│   │   ├── config.js                    # Shared: auto-detects API base URL / mount prefix
│   │   ├── api.js                       # Shared: generic fetch wrapper + error normalization
│   │   ├── i18n.js                      # JEE-only: en/hi/gu/kn string dictionary + t()
│   │   ├── landing.js                   # Landing-page-only: renders the exam-picker cards
│   │   └── app.js                       # JEE-only: JEE's own SPA logic (COMEDK/KCET each have their own app.js)
│   ├── manifest.json                  # Shared PWA manifest (text is JEE-flavored/stale — see frontend README)
│   └── sw.js                           # Shared service worker (app-shell cache; has a known-broken KCET path, see docs/API.md)
│
├── tests/                           # Unit tests + tests/golden/: 297 characterization cases covering all 3 exams
│   ├── test_api.py, test_recommender.py, test_enhancements.py
│
└── screenshots/hero.png             # Used in this README
```

**Why files live where they do:** everything under `app/disha/<exam>/` and `templates/disha_templates/<exam-or-root>` for a given exam is meant to be self-contained enough to copy wholesale into a new exam's folders (see [Adding a new exam](#adding-a-new-exam)). `js/config.js`, `js/api.js`, and `css/style.css` at the top level of `templates/disha_templates/js`/`css` are the only pieces every exam currently shares; everything else that looks shared (`js/i18n.js`) is in practice JEE-only because no other exam adopted it.

---

## Backend / API documentation

Full endpoint-by-endpoint, field-by-field documentation — including the exact differences between JEE's `opening_rank`/`closing_rank` pair, COMEDK's single `cutoff_rank` + `GM`/`KKR` quota, and KCET's single `cutoff_rank` + Karnataka category codes — lives in **[docs/API.md](docs/API.md)**. Read it before integrating against, or extending, any exam's API.

Quick orientation:

| | JEE | COMEDK | KCET |
|---|---|---|---|
| Prefix | *(none — mounted at root)* | `/api/comedk` | `/api/kcet` |
| Meta | `GET /api/meta` | `GET /api/comedk/meta` | `GET /api/kcet/meta` |
| Recommend | `GET`/`POST /api/recommend` | `POST /api/comedk/recommend` | `POST /api/kcet/recommend` ⚠️ 500s today |
| Stats | `GET /api/stats` | `GET /api/comedk/stats` | `GET /api/kcet/stats` |
| Health | `GET /api/health` *(global, no per-exam equivalent)* | — | — |

**Data sources:** JEE's cutoffs come from JoSAA 2025 round-wise data (all 6 rounds, all categories) published by UTMT, sourced originally from the [atmabodha/OpenNLP](https://github.com/atmabodha/OpenNLP) dataset. COMEDK's and KCET's CSVs (`app/disha/comedk/data/comedk_2025.csv`, `app/disha/kcet/data/kcet_2025.csv`) are committed directly into the repo; nothing in the code fetches or refreshes any of the three CSVs at runtime or on a schedule — updating a dataset means replacing the CSV file and, for JEE, rerunning through `data_loader.py`'s round-wise MIN/MAX logic (which happens automatically on next load, no separate build step). This tool is for guidance only and does not guarantee admission outcomes.

---

## Adding a new exam

Read the [Architecture](#architecture-overview) section first. This is **partly config-driven and partly still copy-and-adapt**, and it is worth knowing which is which:

- **Registration is config-driven.** `app/disha/registry.py` is the single place an exam is declared; router mounting and page routes are generated from it. You do not hand-write route handlers.
- **Ordering, capping and top-rank detection are shared.** `app/disha/core/curation.py` serves all exams; do not reimplement them.
- **The pipeline itself is still per-exam.** You write your own `data_loader.py`, `recommender.py` and `schemas.py`, because the genuine domain differences (cutoff shape, eligibility axes, brand signal) live there.
- **The frontend is still fully copy-and-adapt**, and it is the expensive half.

Before you start, read [tests/golden/README.md](tests/golden/README.md) and add your exam to the matrix — the safety net is only as good as its coverage.

**Hard constraint, followed by COMEDK and enforced by this doc: never modify an existing exam's files while adding a new one.** JEE's files were not touched to build COMEDK; COMEDK's files should not be touched to build a fourth exam. Every exam's directory is additive.

### Backend — new files under `app/disha/<new_exam>/`

Use COMEDK as the template to copy the *shape* of (not the literal file contents — COMEDK's numbers are COMEDK-specific), since it's the more complete second implementation:

1. **`__init__.py`** — empty/placeholder, mirrors every other exam package.
2. **`config.py`** — a `Settings` class with your data file path and every tuning constant your recommender needs (band widths, sigma, caps). Do **not** import or extend JEE's or COMEDK's `Settings` — each exam's config is deliberately standalone so tuning one can't silently move another (see the docstring at the top of `app/disha/comedk/config.py`). Think hard about whether your exam publishes an opening/closing rank pair (→ you can reuse JEE's fixed-margin approach) or a single cutoff (→ you'll need COMEDK's clamped-band approach, or something new — read the rationale comments in `comedk/config.py` before picking constants).
3. **`states.py`** — your own branch-family classifier and, if relevant, career-goal weights and any geography/quota logic your exam needs (home-state quotas, regional reservation codes, etc.). Decide up front whether a programme maps to one branch family (COMEDK's approach — programme names are specific enough) or a *set* of tags (JEE's approach — needed because JEE's names are more generic). Don't assume KCET's `app/disha/states` import pattern is a model to copy — KCET reuses JEE's shared `app.disha.states` for goals/labels in one place while defining its own `classify_branch` locally, which is part of why it ended up inconsistent; pick one pattern deliberately instead of mixing them.
4. **`data_loader.py`** — parse your CSV into a flat list of dicts or a small dataclass (COMEDK went with dicts; JEE uses a frozen `dataclass`). Cache the parsed result (`lru_cache` or a module-level global — both patterns exist in this repo) so you're not re-parsing the CSV on every request. Derive anything you can from the data itself rather than hard-coding it — COMEDK's quota list, institute brand tiers, and per-quota competitiveness percentiles are all computed from the CSV at load time, not hand-maintained lists.
5. **`recommender.py`** — the actual filter → bucket (Safe/Target/Reach) → score → sort pipeline. This is where you'll spend the most time re-deriving constants, because JEE's `UPPER_MARGIN`/`LOWER_MARGIN`/`SAFE_FRACTION` are tuned against a real opening→closing *window*, and that window doesn't exist for a single-cutoff exam — copying JEE's numbers verbatim onto a single cutoff produces the exact bucket-explosion/no-backups failure modes documented in `comedk/config.py`'s docstring. Re-derive, don't copy.
6. **`schemas.py`** — request/response Pydantic models. Decide explicitly whether to mirror an existing exam's response field names (COMEDK kept JEE's legacy field names like `safe`/`target`/`reach` for frontend compatibility, then added new JEE-parallel fields alongside them) or start clean. **Whatever fields your request model declares, make sure your recommender only reads fields that actually exist on it** — this is exactly the mistake that currently breaks KCET's `/recommend` (it reads `req.goal` on a schema with no `goal` field). Test the endpoint with `TestClient` before considering it done.
7. **`stats_loader.py`** — a `compute_<exam>_stats()` function feeding the exam's `/stats` dashboard. Fine to leave placeholder/empty keys for anything you don't compute yet (both COMEDK and KCET do this), but say so in a comment rather than leaving it silently blank.
8. **`routes.py`** — an `APIRouter(prefix="/api/<new_exam>")` with `meta`, `stats`, and `recommend` endpoints (page routes for the exam's HTML live in the *root* `app/disha/routes.py`, not here — see below).
9. Wire it in: add one `ExamRegistration` entry to **`app/disha/registry.py`** — id, label, page route + template, stats route + template, and your `APIRouter`. Router mounting and both page routes are generated from that entry; `app/disha/routes.py` needs no edit at all. `tests/test_page_routes.py` will start covering your exam automatically, and will fail if a template path is wrong.

### Frontend — new files under `templates/disha_templates/<new_exam>/`

1. **`<new_exam>/index.html`** — copy an existing exam's HTML shell (COMEDK's is the more complete second example) and adapt the form fields to your exam's inputs. Reuse `../css/style.css` (don't fork the stylesheet — every exam so far reuses it as-is) and load `../js/config.js` + `../js/api.js` (both are genuinely shared and require no changes). Skip `../js/i18n.js` unless you're prepared to build out translated strings for your exam too — COMEDK deliberately didn't, and is English-only as a result.
2. **`<new_exam>/js/app.js`** — copy an existing exam's `app.js` as your starting structure (view-state machine, guided-flow steps, results rendering, share/print, Choice List/bookmarking) and adapt every domain-specific piece: what the guided-flow steps ask for, what payload shape `buildPayload()` sends to `POST /api/<new_exam>/recommend`, and how result cards render your exam's cutoff shape (a rank *bar* against a single cutoff, like COMEDK, vs. a rank *ruler* against an opening/closing window, like JEE). Leave a header comment stating what you ported from and what you adapted — every existing exam's `app.js` does this, and it's what let this doc reconstruct the porting history accurately.
3. **`<new_exam>/stats.html`** — copy an existing stats dashboard and point its `fetch()` calls at `/api/<new_exam>/stats`.
4. Register the new exam in **`templates/disha_templates/js/landing.js`**'s `EXAMS` array (the only shared frontend file you should need to touch) so it shows up as a card on the landing page.
5. Add your new HTML/JS paths to **`templates/disha_templates/sw.js`**'s `APP_SHELL` precache list and its navigation-routing `if`/`else if` chain — and **double-check the path you add there is the file's real path** (e.g. `kcet/index.html`, not a flattened `kcet.html`); the existing KCET entry has exactly this mistake today (see [docs/API.md](docs/API.md#page-routes-html-not-json)) and it's an easy one to repeat.

### The honest cost

Cheaper than it was, but not yet cheap.

**Now free:** route registration, page routes, bucket ordering, per-institute capping, top-rank detection, and page-route test coverage.

**Still real work:** a `config.py` with constants re-derived from your own dataset (do not copy another exam's — read the rationale in `comedk/config.py` for why), a `recommender.py` with a deliberately chosen bucketing model, a `data_loader.py`, and `schemas.py`.

**Still expensive:** the frontend. `kcet/js/app.js` and `comedk/js/app.js` are ~99% identical after normalising renames, so a fourth exam means copying ~2,280 more lines of HTML+JS — and inheriting the copy-paste bugs listed in [tests/golden/README.md](tests/golden/README.md). Consolidating the three frontends behind one shell is the next high-value step, and is deliberately deferred: unlike the backend, there is no cheap way to prove a rewritten SPA renders identically, so it needs a DOM-snapshot harness first.

---

## Configuration reference

All settings are hard-coded Python class attributes — there is deliberately no `.env` file for local dev.

**JEE** — `app/disha/config.py::Settings`

| Setting | Default | Notes |
|---|---|---|
| `cors_origins` | `"*"` | Comma-separated allow-list, or `*`. Not overridable via env var today (see caveat in Setup). |
| `data_path` | `app/disha/data/JEE_2025_Cutoffs.xlsx` | **File does not exist in this repo** — a legacy Excel path kept only for reference; nothing reads it. |
| `basic_merged_data_path` | `app/disha/data/josaa_merged_2025.csv` | The actual, only data source JEE loads. |
| `data_mode` | `"basic"` | Permanently `"basic"` — an "extended" multi-year mode was fully removed; the setting survives for API compatibility. |

**COMEDK** — `app/disha/comedk/config.py::Settings` — a much larger set of tuned constants (target/reach band floors/ceilings, sigma bounds, per-institute curation caps) with extensive rationale comments explaining *why* each clamp exists. Read the file directly rather than a table here — the comments are the documentation.

**KCET** — no `config.py` exists; its tuning constants are inline in `app/disha/kcet/recommender.py`.

---

## Testing

```bash
pytest tests/ -v
```

- `tests/test_api.py` — HTTP-level tests against JEE's `/api/health`, `/api/meta`, `/api/recommend` (filters, language handling, validation errors).
- `tests/test_recommender.py` — unit tests for JEE's bucketing, quota/gender filtering, and overqualification pruning.
- `tests/test_enhancements.py` — unit tests for JEE's region/metro classification and interest-score blending.

No test file exists for `app/disha/comedk/` or `app/disha/kcet/` — if you're changing either, you're currently relying on manual verification (e.g. `TestClient` in a scratch script, as used to verify the KCET bug documented above) rather than an existing suite catching regressions.

---

## Portal integration

See [DISHA_INTEGRATION_QA.md](DISHA_INTEGRATION_QA.md) for the full Q&A on plugging Disha (all three exams — one `include_router()` call brings all of them, per the Architecture section above) into a larger FastAPI portal.

---

## License

MIT License — see [LICENSE](LICENSE).
