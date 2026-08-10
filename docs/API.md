# API Reference

> **Docs-sync reminder:** if you change a request/response field, a route path, or a status code below, update this file *and* the relevant summary in the root [README.md](../README.md) in the same change. See [CONTRIBUTING.md](../CONTRIBUTING.md).

This document describes every HTTP endpoint currently exposed by the FastAPI backend, for all three exam engines (JEE, COMEDK, KCET), as read directly from `app/disha/**/routes.py` and `app/disha/**/schemas.py` on 2026-08-10. Interactive, always-up-to-date schemas are also available at `/api/docs` (Swagger) and `/api/redoc` whenever the server is running.

All routes below are relative to wherever `disha_router` is mounted. In standalone dev (`main.py`) that's the root (`/`); inside the UTMT portal it's whatever prefix is chosen (e.g. `/learning_games`) — see the root README's "Setup" and "Portal integration" sections.

---

## Contents

- [Global / JEE endpoints](#global--jee-endpoints)
- [COMEDK endpoints](#comedk-endpoints)
- [KCET endpoints](#kcet-endpoints)
- [Page routes (HTML, not JSON)](#page-routes-html-not-json)
- [Cross-exam data-shape comparison](#cross-exam-data-shape-comparison)

---

## Global / JEE endpoints

Defined in `app/disha/routes.py`. These are the only routes without a per-exam prefix — they are also, in effect, "the JEE API" (JEE was the original/only exam and never got a `/api/jee` prefix).

### `GET /api/health`

Liveness probe. Also used as `render.yaml`'s `healthCheckPath`.

```json
{ "status": "ok", "programs": 12143 }
```

### `GET /api/meta`

Form metadata for the JEE frontend: valid states, career goals, genders, reservation categories, and branch-preference families, plus the active dataset size.

Response (`MetaResponse`):

```json
{
  "states": ["Andhra Pradesh", "Arunachal Pradesh", "..."],
  "goals": [
    { "value": "coding", "label": "Software / coding career" },
    { "value": "research", "label": "Research / higher studies" },
    { "value": "pure_science", "label": "Pure Science (Physics, Chemistry, Maths)" },
    { "value": "mba", "label": "Management / MBA / business" },
    { "value": "core", "label": "Core engineering" },
    { "value": "undecided", "label": "Undecided / keeping options open" }
  ],
  "genders": ["male", "female"],
  "categories": [
    { "value": "OPEN", "label": "General (OPEN / CRL Category Rank)", "available": true },
    { "value": "OBC-NCL", "label": "OBC-NCL", "available": true },
    { "value": "SC", "label": "SC (Scheduled Caste)", "available": true },
    { "value": "ST", "label": "ST (Scheduled Tribe)", "available": true },
    { "value": "EWS", "label": "EWS (Economically Weaker Section)", "available": true },
    { "value": "OPEN (PwD)", "label": "OPEN (PwD)", "available": true }
  ],
  "branches": [{ "value": "cs_it", "label": "CS / IT" }, "..."],
  "total_programs": 12143,
  "data_mode": "basic",
  "allow_toggle": false,
  "extended_available": false
}
```

`data_mode`/`allow_toggle`/`extended_available` are permanently `"basic"`/`false`/`false` — an older multi-year "extended" dataset was removed; these fields survive only so old frontend builds don't crash on missing keys. `RecommendRequest.data_mode` is likewise accepted but ignored server-side.

### `GET|POST /api/recommend`

The core recommendation endpoint. **Both HTTP methods work** — this is one of the real differences from COMEDK/KCET, which are POST-only.

- **POST** takes a JSON body validated as `RecommendRequest` (`app/disha/schemas.py`).
- **GET** takes the same fields as query parameters, with defaults (`gender=male`, `home_state=Delhi`, `goal=coding`, `seat_category=OPEN`) so a bare `GET /api/recommend?mains_rank=6000` works. The GET path is a convenience wrapper — it builds a `RecommendRequest` from the query params and calls the same `recommend()` function.

Request fields (`RecommendRequest`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `adv_rank` | int ≥ 1, optional | — | JEE Advanced CRL rank. Needed to see IITs. |
| `mains_rank` | int ≥ 1, optional | — | JEE Mains CRL rank. Needed to see NITs/IIITs/GFTIs. At least one of `adv_rank`/`mains_rank` is required — the request fails validation (422) otherwise. |
| `gender` | `"male" \| "female"` | required | |
| `home_state` | string | required | Must match (case-insensitively) one of `states.INDIAN_STATES`; normalized to the canonical spelling. |
| `goal` | `coding\|research\|mba\|core\|undecided\|pure_science` | required | |
| `data_mode` | `"basic" \| "extended"` | `"basic"` | Accepted, but always resolved to `"basic"` server-side. |
| `seat_category` | string | `"OPEN"` | One of `OPEN, OBC-NCL, SC, ST, EWS` or the `" (PwD)"`-suffixed variant of each. |
| `is_pwd` | bool | `false` | Deprecated — appends `" (PwD)"` to `seat_category` if not already present. Kept for API compatibility. |
| `brand_branch_ratio` | float 0.0–1.0 | `0.5` | 0 = weight branch-fit only, 1 = weight institute brand only. |
| `branch_preferences` | string[] | `[]` | Branch-family codes, e.g. `["cs_it", "ece"]`. Empty = no filter. |
| `bucket` | string, optional | `"all"` | `safe\|target\|dream\|all`. **Note:** this field exists on the schema but the recommender does not filter by it — see caveat below. |
| `college_type` | string, optional | `"all"` | `IIT\|NIT\|IIIT\|GFTI\|all`. Same caveat as `bucket`. |
| `page` / `page_size` | int | `1` / `50` | **Accepted but not applied** — see caveat below. |
| `max_results` | int | `5000` | **Accepted but not applied** — see caveat below. |
| `lang` | `en\|hi\|gu\|kn` | `"en"` | Language for all generated text (guidance, notes, `fit_label`, `reason`). |

> **Known caveat (verified against `app/disha/recommender.py`):** `page`, `page_size`, `max_results`, `bucket`, and `college_type` are accepted by the schema and, for `bucket`/`college_type`, forwarded from the query-param GET path onto the request object — but `recommender.recommend()` never reads any of them. Every call returns **every** matching program in one response (`page`/`page_size`/`total_pages` stay `null`). The JEE frontend (`js/app.js`) compensates by sending a generous `max_results: 150` and rendering everything client-side; it does not actually rely on server-side pagination. This is a real gap between the documented schema and the implemented behavior — if you add real pagination, update this table.

Response (`RecommendResponse`) — abbreviated:

```json
{
  "guidance": "Found 45 eligible institute-branch options...",
  "interest_guidance": "Since you are aiming for a software/coding career...",
  "counts": {
    "total": 45,
    "shown": 45,
    "by_category": { "Safe": 15, "Target": 20, "Reach": 10 },
    "by_type": { "IIT": 10, "NIT": 20, "IIIT": 10, "GFTI": 5, "total": 45 }
  },
  "notes": [],
  "category_guidance": [
    { "category": "Target", "count": 20, "blurb": "These match your rank closely..." }
  ],
  "recommendations": [
    {
      "institute": "National Institute of Technology, Jalandhar",
      "institute_type": "NIT",
      "institute_state": "Punjab",
      "exam": "mains",
      "branch": "Computer Science and Engineering",
      "branch_full": "Computer Science and Engineering (4 Years, Bachelor of Technology)",
      "degree": "Bachelor of Technology",
      "quota": "OS",
      "gender_pool": "neutral",
      "opening_rank": 6200,
      "closing_rank": 9500,
      "category": "Target",
      "fit_label": "Achievable - your rank lies within last year's opening to closing range.",
      "interest_score": 8.9,
      "matched_interest": true,
      "home_state_advantage": null,
      "female_seat_advantage": null,
      "confidence": "stable_drift",
      "flag_round": null,
      "reason": "Target for you – strong fit for your goal...",
      "region": "north",
      "is_metro": false,
      "is_top_iit": false,
      "history": { "2025": 9500 },
      "admission_probability": 88.2,
      "is_preparatory": false,
      "has_preparatory_rounds": false
    }
  ],
  "page": null,
  "page_size": null,
  "total_count": 45,
  "total_pages": null,
  "total_by_type": { "safe": { "...": 0 }, "target": { "...": 0 }, "dream": { "...": 0 }, "all": { "...": 0 } },
  "thresholds": { "lower_margin": 0.35, "safe_fraction": 0.15, "upper_margin": 0.25 }
}
```

Key points specific to JEE:
- Every option carries a genuine **`opening_rank` / `closing_rank` pair** sourced from JoSAA's round-wise columns (`Opening_R1…R6` / `Closing_R1…R6` — opening = min, closing = max across rounds).
- `category` is one of `Safe | Target | Reach` (`Reach` is shown to users as "Dream").
- `confidence` is one of JEE's volatility tags (`highly_stable | stable_drift | volatile_vacancy | volatile_erratic`) — a per-program label of how much its closing rank moved across 2025's rounds, not a generic three-level word.
- `home_state_advantage` / `female_seat_advantage`: rank cushion (in ranks) that the HS quota or a female-only seat gives vs. the equivalent open-pool seat, when applicable; `null` otherwise.
- `seat_category` (request) maps 1:1 to `seat_type` filtering — there is no partial/fuzzy category matching.

### `GET /api/stats`

Dynamically computed dataset statistics for the Insights dashboard (`/stats` page). Computed fresh from `josaa_merged_2025.csv` on every request (not cached) via `app/disha/stats_loader.py`. Returns institute-type counts, state counts, quota/seat-type/gender breakdowns, round-wise average closing ranks, top/bottom cutoffs, per-type institute competitiveness, CSE-vs-non-CSE cutoff premium, volatility-tag counts, gender-advantage multipliers, and rank-availability curves. See `compute_dataset_stats()` for the authoritative field list — the response has no Pydantic model (`-> dict`), so its shape is not enforced by a schema and can drift without triggering a 422 anywhere.

### API docs

- `GET /api/docs` — Swagger UI
- `GET /api/redoc` — ReDoc
- `GET /api/openapi.json` — raw OpenAPI schema

---

## COMEDK endpoints

Defined in `app/disha/comedk/routes.py`, mounted under `APIRouter(prefix="/api/comedk")`.

### `GET /api/comedk/meta`

```json
{
  "quotas": ["GM", "KKR"],
  "goals": [],
  "branch_families": [
    { "value": "cse", "label": "Computer Science & Engineering" },
    { "value": "ai_ds", "label": "AI / Data Science / ML" },
    { "value": "cyber", "label": "Cyber Security / Blockchain / IoT" },
    "... (18 families total, see app/disha/comedk/states.py)"
  ],
  "total_programs": 2384
}
```

`quotas` is **derived from the loaded CSV at runtime** (`sorted({p["quota"] for p in get_programs()})`), not hard-coded — if a future COMEDK dataset adds a third quota, it will appear here automatically. `goals` is always `[]`: COMEDK dropped the JEE-style "career goal" step in favor of a branch-family multi-select, so there is no goal-based interest scoring in this exam.

### `GET /api/comedk/stats`

Same purpose as JEE's `/api/stats` but computed from COMEDK's single-cutoff dataset (`app/disha/comedk/stats_loader.py::compute_comedk_stats()`). The response includes several always-empty keys (`branch_counts: {}`, `round_averages*: {}`) kept only so the frontend's stats-rendering code — written once against JEE's richer shape — doesn't have to special-case COMEDK.

### `POST /api/comedk/recommend`

**POST only** — there is no GET/query-param convenience form here, unlike JEE.

Request fields (`ComedkRecommendRequest`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `rank` | int ≥ 1 | required | COMEDK rank. |
| `quota` | string | `"GM"` | `GM` (General Merit) or `KKR` (Kalyana Karnataka Region) — see comparison table below. |
| `branch_families` | string[] | `[]` | Family codes from `/api/comedk/meta`'s `branch_families`. |
| `bucket` | string, optional | `"all"` | `safe\|target\|reach\|all` — **this one is actually applied** (unlike JEE's same-named field). |
| `page` / `page_size` | int | `1` / `50` | **Actually applied** — COMEDK's `recommend()` slices the filtered+bucketed list by `page`/`page_size` and sets `has_next` accordingly. |
| `lang` | `en\|hi\|gu\|kn` | `"en"` | Accepted by the schema, but the current COMEDK frontend (`comedk/js/app.js`) always sends `"en"` — there is no language switcher in the COMEDK UI. |

Response (`ComedkRecommendResponse`) — abbreviated:

```json
{
  "safe": ["... legacy duplicate of the Safe slice of `recommendations` ..."],
  "target": ["..."],
  "reach": ["..."],
  "total_safe": 12,
  "total_target": 8,
  "total_reach": 5,
  "has_next": false,
  "guidance": "Found 25 eligible programmes...",
  "interest_guidance": "",
  "counts": { "total": 25, "shown": 25, "by_category": {"Safe": 12, "Target": 8, "Reach": 5}, "by_type": {} },
  "notes": [],
  "category_guidance": [{ "category": "Target", "count": 8, "blurb": "..." }],
  "recommendations": [
    {
      "institute": "R V College of Engineering",
      "program": "Computer Science and Engineering (4 Years, Bachelor of Technology)",
      "quota": "GM",
      "cutoff_rank": 692.0,
      "bucket": "Target",
      "tags": [],
      "category": "Target",
      "fit_label": "...",
      "reason": "...",
      "admission_probability": 61.3,
      "confidence": "medium",
      "interest_score": 0.0,
      "matched_interest": false,
      "rank_gap": 192,
      "brand_score": 1.0,
      "brand_tier": "elite",
      "is_metro": true,
      "kkr_gap": 1450.0,
      "branch": "Computer Science and Engineering",
      "branch_family": "cse",
      "degree": "Bachelor of Technology"
    }
  ],
  "total_count": 25,
  "total_by_type": {},
  "thresholds": {}
}
```

`interest_guidance` is always `""` and `matched_interest`/`interest_score` are effectively unused (COMEDK has no goal step) — they exist purely because `ComedkProgramNode` was built as a structural mirror of JEE's `Recommendation` model. `safe`/`target`/`reach`/`total_safe`/`total_target`/`total_reach`/`has_next` are the **legacy field names the current frontend actually reads**; `recommendations`/`counts`/`category_guidance` are the newer JEE-parallel fields, present but not yet consumed by `comedk/js/app.js`. Both sets describe the same underlying data.

**How the single cutoff is turned into Safe/Target/Reach** (`app/disha/comedk/recommender.py`, tuned via `app/disha/comedk/config.py`): with `gap = cutoff_rank - rank`, a program is `None` (dropped) if `gap < -reach_band(cutoff)`, `Reach` if `gap < 0`, `Target` if `gap < target_band(cutoff)`, else `Safe` — where `target_band`/`reach_band` are the student's cutoff scaled by a fixed fraction and then **clamped** into an absolute rank range (e.g. target band is `clamp(0.15 × cutoff, floor, 6000)`). This clamping exists specifically because a single published cutoff, unlike JEE's opening/closing pair, has no naturally observed "admitted window" — see the long comment in `comedk/config.py` for the worked example of why an unclamped fraction breaks at both ends of the rank range.

---

## KCET endpoints

Defined in `app/disha/kcet/routes.py`, mounted under `APIRouter(prefix="/api/kcet")`.

### `GET /api/kcet/meta`

```json
{
  "quotas": ["1G", "1K", "1R", "2AG", "..."],
  "goals": [
    { "value": "coding", "label": "Software / coding career" },
    "... (reuses the same 6 goals as JEE, from app.disha.states)"
  ],
  "total_programs": 18850
}
```

### `GET /api/kcet/stats`

Same shape/purpose as COMEDK's `/api/comedk/stats`, computed from `app/disha/kcet/data/kcet_2025.csv` via `app/disha/kcet/stats_loader.py`.

### `POST /api/kcet/recommend` — **currently broken (500 on every call)**

> **Verified bug, not a guess:** `KcetRecommendRequest` (`app/disha/kcet/schemas.py`) has no `goal` field. `app/disha/kcet/recommender.py` line 86 calls `_matches_goal(prog, req.goal)`, which raises `AttributeError: 'KcetRecommendRequest' object has no attribute 'goal'` for every request — Pydantic silently drops the unrecognized `goal` key from the incoming JSON instead of rejecting it. This was reproduced directly against this repo (`TestClient(app).post("/api/kcet/recommend", json={...})` → `500 Internal Server Error`) while writing this document. `templates/disha_templates/kcet/js/app.js` *does* send `goal` in every request, so the KCET results page is currently non-functional end-to-end, even though it's linked from the landing page like a finished exam. Fixing this is an application-code change, out of scope for this docs pass — flagging it here so the contract below isn't mistaken for verified-working behavior.

Request fields as written (`KcetRecommendRequest`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `rank` | int ≥ 1 | required | KCET rank. |
| `quota` | string | `"GM"` | See quota-code table below. |
| `branches` | string[] | `[]` | Accepted by the schema; **not read by the recommender** — filtering is done by `goal` keyword-matching instead (see bug above), not by this field. |
| `bucket` | string, optional | `"all"` | `safe\|target\|reach\|all`. |
| `page` / `page_size` | int | `1` / `50` | Applied **only to the `safe` list** — `target`/`reach` are always returned in full, an inconsistency vs. both JEE (no pagination at all) and COMEDK (pagination applied uniformly across the selected bucket). |

Response (`KcetRecommendResponse`) — the smallest/least-developed of the three:

```json
{
  "safe": [
    { "institute": "...", "program": "...", "quota": "1G", "cutoff_rank": 7516.0, "bucket": "Safe", "tags": [] }
  ],
  "target": ["..."],
  "reach": ["..."],
  "total_safe": 0,
  "total_target": 0,
  "total_reach": 0,
  "has_next": false
}
```

There is no `guidance`, `notes`, `category_guidance`, `admission_probability`, `fit_label`, `reason`, `brand_score`, or `lang` support in KCET's response — none of COMEDK's JEE-parallel additive fields were ported over.

**Bucketing logic** (when it runs, ignoring the `goal` bug): purely ratio-based off the single `cutoff_rank`, relative to the student's `rank` — no probability model, no brand/institute tiering, no textual reason. See `app/disha/kcet/recommender.py::_categorize()` for the exact multipliers.

**Quota codes — meaning not fully verified.** The dataset (`app/disha/kcet/data/kcet_2025.csv`) contains category codes crossing a reservation tier (`GM`, `1G`, `1K`, `1R`, `2AG`, `2AK`, `2AR`, `2BG`, `2BK`, `2BR`, `3AG`, `3AK`, `3AR`, `3BG`, `3BK`, `3BR`, `SCG`, `SCK`, `SCR`, `STG`, `STK`, `STR`, and possibly `GMK`/`GMR`) with a one-letter regional suffix. Based on KEA's published category scheme this is very likely reservation category (`GM`/`1`/`2A`/`2B`/`3A`/`3B`/`SC`/`ST`) × home-region (blank/`K`=Kalyana Karnataka/`R`=rest of state), but **no code comment or docstring in this repo states that explicitly** — treat the suffix meaning as unconfirmed until checked against an official KEA cutoff sheet, rather than repeating this guess as fact elsewhere.

---

## Page routes (HTML, not JSON)

All defined with `include_in_schema=False`, so they don't show up in `/api/docs`. Registered in `app/disha/routes.py` unless noted.

| Route | Serves |
|---|---|
| `GET /` | `templates/disha_templates/index.html` (registered in `main.py`, not `routes.py`) |
| `GET /stats` | `templates/disha_templates/stats.html` (JEE insights dashboard) |
| `GET /exam/jee` | `templates/disha_templates/jee.html` |
| `GET /exam/kcet` | `templates/disha_templates/kcet/index.html` |
| `GET /exam/kcet/stats` | `templates/disha_templates/kcet/stats.html` |
| `GET /exam/comedk` | `templates/disha_templates/comedk/index.html` |
| `GET /exam/comedk/stats` | `templates/disha_templates/comedk/stats.html` |
| `GET /{full_path}` | Catch-all in `main.py`: serves any real static file under `templates/disha_templates/` at that path, or falls back to `index.html` for extension-less ("navigation-like") paths, or a plain 404 for missing extensioned paths. |

> **Known bug, verified:** the service worker (`templates/disha_templates/sw.js`) maps in-app navigation to `/exam/kcet` onto a fetch for `${basePath}/kcet.html` — a flat filename that **does not exist** (the real file is `kcet/index.html`, served only via the `/exam/kcet` route above). Confirmed with `TestClient(app).get("/kcet.html")` → `404`, vs. `GET /exam/kcet` → `200`. First-load navigation (before the service worker controls the page) still works because the browser requests `/exam/kcet` directly; the bug only bites once the SW is installed and intercepting.

---

## Cross-exam data-shape comparison

This is the honest side-by-side the task asked for — read this before assuming any one exam's contract generalizes to the others.

| Aspect | JEE | COMEDK | KCET |
|---|---|---|---|
| Cutoff shape | **Pair**: `opening_rank` + `closing_rank`, derived at runtime as MIN/MAX across 6 rounds | **Single**: `cutoff_rank` (`Closing_R1`; `Opening_R1` exists in the CSV but is assumed equal and unused) | **Single**: `cutoff_rank` (only round 1 present in the data) |
| Reservation dimension | `seat_category` — canonical values `OPEN / OBC-NCL / SC / ST / EWS`, each with a `" (PwD)"` variant | `quota` — `GM` (General Merit) / `KKR` (Kalyana Karnataka Region) | `quota` — Karnataka category codes crossed with a regional suffix (~22–24 distinct values, see caveat above) |
| Career-goal step | Yes — `goal` drives `interest_score` / `matched_interest` via a tag-weight model | No — replaced with a `branch_families` multi-select filter; `goals` in meta is always `[]` | Nominally yes (reuses JEE's `goal` values in `/meta`) but **the request schema has no `goal` field**, which is why `/recommend` 500s (see bug above) |
| Home-state / gender quota | Yes — HS/OS/GO/JK/LA quotas, female-only seat pool, both surfaced as `*_advantage` rank cushions | No — all COMEDK colleges are in Karnataka, so there's no home-state axis; no gender pool either | No home-state/gender modeling found |
| Bucketing method | Fixed absolute-rank thresholds off the real opening/closing window (`UPPER_MARGIN`/`LOWER_MARGIN`/`SAFE_FRACTION`) | Cutoff-relative bands **clamped** into an absolute rank range (`target_band`/`reach_band` in `comedk/config.py`) — deliberately different math because there's no real "window" to measure | Simple fixed ratio multipliers on the single cutoff (e.g. `cutoff < rank × 0.85` → Reach) — no clamping, no probability curve |
| Admission probability | Sigmoid over `(closing_rank − rank) / σ`, `σ` from historical round-to-round volatility | Sigmoid over `(cutoff − rank) / σ`, `σ` a clamped fraction of the cutoff (stated as an assumption, not fitted — see `comedk/config.py`) | Not computed at all |
| Server-side pagination | Accepted (`page`/`page_size`/`max_results`) but **not applied** — full result set returned every time | **Applied** across the selected bucket | Applied **only** to the `safe` list |
| Response fields | Rich: `fit_label`, `reason`, `region`, `is_metro`, `is_top_iit`, `history`, `is_preparatory`, volatility-tag `confidence` | Additive superset of JEE's shape plus COMEDK-only fields (`kkr_gap`, `brand_tier`, `rank_gap`) — JEE-parallel fields present but not all consumed by the frontend yet | Minimal: `institute`, `program`, `quota`, `cutoff_rank`, `bucket`, `tags` only |
| Language support | `en/hi/gu/kn`, both static UI strings (`js/i18n.js`) and backend-generated text (`lang` request field) | Backend accepts `lang`, but the frontend never sends anything but `"en"` — effectively English-only in practice | No `lang` field on the request or response at all |

If you add a fourth exam, expect to make the same kind of shape decision COMEDK and KCET each made independently — there is currently no shared schema or shared recommender base class enforcing consistency across exams. See the root README's "Adding a new exam" section.
