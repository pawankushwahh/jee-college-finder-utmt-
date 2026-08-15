# Golden baseline

Characterization tests for the multi-exam refactor. They pin the **current**
API responses so a structural change can be proven not to alter behaviour.

These are not correctness tests. They assert nothing about whether a
recommendation is *good* — only that it is *unchanged*. A frozen bug stays
frozen on purpose; see "Known frozen behaviour" below.

## Why this exists

Before this directory, `tests/` covered JEE only — KCET and COMEDK had **no
automated coverage at all**, and six of the JEE tests had been failing
silently against constants that had since moved. Refactoring three engines
into one shared core without a baseline would have been unverifiable.

## Usage

Capture the baseline (do this **before** a refactor step):

```bash
python -m tests.golden.capture
```

Verify nothing changed (run after **every** step):

```bash
pytest tests/golden -q
```

## When a case fails

A failure means the response changed. Two possibilities:

1. **Unintended** — the refactor broke something. Fix the code.
2. **Intended** — you meant to change behaviour. Re-run the capture script
   and review the resulting `git diff`. That diff *is* the behaviour change,
   and it belongs in its own commit with its own justification, never mixed
   into a refactor.

## Layout

| Path | Purpose |
|---|---|
| `matrix.py` | The request matrix — which inputs are pinned, and why |
| `capture.py` | Writes the baseline |
| `test_golden.py` | Replays it and asserts byte-equality |
| `manifest.json` | sha256 of each source CSV + per-exam case counts |
| `jee/ kcet/ comedk/` | One JSON per request, named by a hash of the request |

## Coverage

297 cases: 192 JEE, 70 KCET, 35 COMEDK, plus every `/meta`, `/stats` and
`/health` endpoint.

The matrix uses a **core grid** (a full cross-product of the axes that
genuinely interact — rank, seat category, and which ranks the student
supplied) plus **one-axis-at-a-time variations** for everything else. A full
cross-product of the JEE axes alone is ~32,000 cases and reveals nothing more,
because language and pagination don't interact with row eligibility.

Edge cases are pinned explicitly, each with a comment naming the code path it
holds still. Some examples:

- JEE `adv_only` / `mains_only` / `both` — pins `_relevant_rank()`, where IIT
  rows read `adv_rank` and everything else reads `mains_rank`
- JEE `ST (PwD)` vs `OPEN` — the rank scale differs by four orders of
  magnitude between categories (116 vs 937,704)
- JEE `home_state="Atlantis"` — the unmatched-state fallback
- COMEDK rank **100 vs 101** — straddles `top_rank_threshold`, the one place
  COMEDK uses a hardcoded rank gate where JEE and KCET derive it from bucket counts
- COMEDK rank 200,001 / KCET rank 400,001 — one past `max_rank`, pinning the
  implausible-rank paths (an early return for COMEDK, a note for KCET)
- KCET `"ZZZ"` — an unknown category code must not crash `parse_category()`

## Determinism

Byte-equality is safe here. Verified, not assumed:

- All three `_order_bucket` sort keys are **total orders**, ending in
  `(institute, branch)` — so ordering can't vary with input order or
  `PYTHONHASHSEED`
- Every float reaching a response is rounded (`round(prob, 1)`, `round(score, 2)`)
- The only set-to-JSON path is `tags`: `sorted()` in KCET, a single-element
  list in COMEDK, absent from JEE's schema
- No `list(set(...))` anywhere in `app/disha/`

Empirically confirmed by capturing twice in separate processes (different
hash seeds) and on both Python 3.9 and 3.13 — all four captures byte-identical.

## Known frozen behaviour

Deliberately preserved so the baseline stays meaningful. Fix these in their
own commits **after** the refactor, updating the goldens as a recorded change:

- `kcet/stats.html:585`, `comedk/stats.html:593` — root-relative `fetch()` and
  no `config.js`, so both break under the `/learning_games` portal mount
- `sw.js:27` — precaches `kcet.html`, which does not exist
- `kcet/js/app.js:255` — a `2AG` student is shown "KKR — Kalyana Karnataka"
- `kcet/js/app.js:523` — `RANK_AXIS_MAX = 200000` clamps a dataset reaching 262,188
- A single late cutoff jump tags as `volatile_erratic` where the original test
  expected `volatile_vacancy` (see `test_recommender.py`)
