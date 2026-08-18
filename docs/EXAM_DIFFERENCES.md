# KCET vs COMEDK — what is shared, and every difference that is not

Both exams run the **same recommendation approach**, in the same six stages:

```
filter by eligibility → categorise into Safe/Target/Reach → score → explain
                      → order each bucket best-first → curate for display
```

They are nevertheless **separate backend modules** (`app/disha/kcet/` and
`app/disha/comedk/`), because their counselling rules genuinely differ. This
file is the inventory of those differences: what each one is, why it exists, and
which file to open to change it. It is written from the code, not from memory —
every number below can be checked against the file named beside it.

The rule this split follows: **the stage's rule lives in `app/disha/core/`, the
stage's inputs and composition live in the exam's own package.** If you find
yourself wanting to write `if exam == "comedk"` in `core/`, the abstraction is
wrong — push the difference into the exam module instead (see
[CONTRIBUTING.md](../CONTRIBUTING.md)).

---

## 1. What the two exams share

Everything here is in `app/disha/core/`, imports nothing from an exam package,
and is unit-tested in `tests/test_core.py`.

| Module | What it decides | Why it can be shared |
|---|---|---|
| `core/rounds.py` | Which of a programme's round-wise cut-offs becomes *the* cut-off (`max` / `last` / `first` / a round number), how round columns are found in a CSV header, how a numeric cell is parsed, and the per-strategy view cache. | Both exams publish one column per round and both default to `max` for the same two reasons — coverage and "the loosest rank actually admitted". |
| `core/scoring.py` | The competitiveness percentile: how much in demand a programme is, relative to the others in its own seat pool. `1.0` is always the lowest cut-off in the group. | Neither exam ships a college tier list, so both fall back to the same signal. Only the grouping column and the tie rule differ, and both are arguments. |
| `core/cutoff.py` | `PointCutoffModel` — band widths, bucket boundaries and the probability curve for a single published cut-off. `RangeCutoffModel` — the same for an observed low/high range. `clamp`. | The formulas are identical; every constant is supplied by the caller. **Neither model has an overqualification prune and neither may gain one** — see the module docstring. |
| `core/curation.py` | Bucket display order, best-first ordering inside a bucket, the institute-diversity cap, the top-rank shortlist, and flattening for display. | These were three character-identical copies before extraction, differing only in attribute names. |
| `registry.py` | Route mounting and page routes per exam. | Pure wiring; says nothing about engine behaviour. |

What is deliberately **not** shared is the *order the stages are composed in*
(see §4.5 and §4.6) and everything in §2–§4 below.

---

## 2. The data, and the counselling rules behind it

| Axis | KCET | COMEDK | Where |
|---|---|---|---|
| Source | KEA cut-off PDFs → `kcet_2025_all_rounds.csv` | Six COMEDK PDFs → `comedk_2025_all_rounds.csv` | [DATA_PIPELINE.md](DATA_PIPELINE.md) |
| Rounds published | 3 | 4, **plus a mock round** | `<exam>/data/` |
| Round symmetry | Near-symmetric: 47 of 48 category codes publish all three rounds (only `1KH` stops after round 2). | **Asymmetric by quota**: GM ran in rounds 1/3/4, KKR in 1/2 only. A GM `max` is taken over three rounds, a KKR `max` over two. | `comedk/data_loader.py` |
| Mock round | None. | Published, but allotted no seat, so it can never be the cut-off. Carried as `mock_rank` and excluded by `core.rounds.ROUND_COLUMN` by construction. | `comedk/data_loader.py` |
| Vacant rows | Rows missing college / course / category / any cut-off are skipped. | Additionally: rows that had seats but never filled in **any** round are dropped as unrecommendable, and non-positive ranks are dropped rather than read as a cut-off of 0. | both `data_loader.py` |
| Cut-off type | Fractional (`76553.5`) — KEA really publishes these, and truncating them silently corrupted 2,366 rows in an earlier loader. | Whole numbers. | `KcetProgram.closing_rank` |
| Extra per-row data | Round-wise history, observed `rank_low` / `rank_high`, `band_imputed`. | Round-wise history, `mock_rank`, seat counts, fees, `kkr_gap`, `is_metro`, institute `brand_tier`. | both `data_loader.py` |

---

## 3. Eligibility, categories and quotas

| Axis | KCET | COMEDK | Where |
|---|---|---|---|
| Eligibility key | Exact category code as printed on the student's KEA rank card. | Quota, derived from the data rather than hardcoded. | `<exam>/recommender.py` |
| Code space | **48 codes**: 8 reservation categories × 3 sub-quotas (`G` state-wide / `K` Kannada-medium / `R` rural) × 2 seat pools. | **2**: `GM`, `KKR`. | `kcet/states.py`, `comedk/data_loader.get_quotas` |
| Second seat pool | 371(j) Kalyana-Karnataka seats are published in a separate KEA document with a parallel code set (`GM`→`GMH`, `1K`→`1KH`). The vocabularies are disjoint, so a code identifies its own pool and no extra request field is needed. | None. KKR is a quota inside one pool, not a second pool. | `kcet/states.split_seat_pool` |
| Code parsing | `parse_category` / `describe_category` split a code into reservation + region for display. | No parsing; the quota is shown as published. | `kcet/states.py` |
| Cross-quota comparison | None. | `kkr_gap` = KKR cut-off − GM cut-off per (institute, branch), surfaced on the card **with its sign reported honestly** — a KKR seat is usually *harder*, not easier. | `comedk/data_loader._compute_kkr_gaps` |
| Branch filter | Optional; a programme carries a **set** of tags, because the source course names are corrupted (`"BLO CK CHAIN"`, `"CYB ER SECURITY"`) and are matched by keyword bag. | Optional; a programme carries **exactly one** family, because COMEDK's course names are clean enough to classify unambiguously. | `kcet/states.classify_kcet_branch`, `comedk/states.classify_branch` |
| Career goal | Part of the request; re-ranks branches via `GOAL_TAG_WEIGHTS`, blended against college quality by `brand_branch_ratio`. | **Removed from the flow.** Branch families filter only; ordering is by option quality alone, and `matched_interest` is always `False`. | `<exam>/recommender.py` |

---

## 4. The engine

### 4.1 Bucketing model

|  | KCET | COMEDK |
|---|---|---|
| Model | `RangeCutoffModel` — buckets read off the **observed** range of ranks admitted across the rounds (`rank_low`…`rank_high`). | `PointCutoffModel` — one cut-off, with the admitted band **modelled** around it. |
| Why | Its rounds are near-symmetric, so the range means the same thing in every category. | Its rounds are not, so a "range" would mean different things in GM and KKR. |
| Single-round programmes | 26% publish only one round, so the loose end is **imputed upward** from bracket-median ratios and flagged `band_imputed`. Very unevenly spread: 4% of GM rows against 54–62% of some 371(j) categories. | Not applicable. |
| Escape hatch | `settings.use_observed_range = False` falls back to `PointCutoffModel` with the constants below. | — |
| Special floor | — | `dynamic_floor_fraction = 0.5`: at a cut-off of 692 a flat 1,000-rank floor would swallow the whole rank range below it and stop top ranks reading as Safe. |

### 4.2 Constants

Shared values: `safe_margin` 0.15, `upper_margin` 0.25, `sigma_fraction` 0.12,
`steepness` 1.5. Everything else is measured per dataset — KCET's cut-off tail
runs to 262,158 against COMEDK's 111,800, so reusing one exam's absolute
ceilings for the other would push everything past the ~90th percentile onto the
ceiling.

| Constant | KCET | COMEDK |
|---|---|---|
| `target_band_floor` / `ceiling` | 1,500 / 13,000 | 1,000 / 6,000 |
| `reach_band_ceiling` | 18,000 | 8,000 |
| `sigma_floor` / `ceiling` | 300 / 11,000 | 150 / 5,000 |
| `max_rank` (typo guard) | 400,000 | 200,000 |

Each `config.py` documents the percentiles behind its own numbers.

### 4.3 Relevance and top-up — KCET only

Observed ranges decide *which* bucket, but not whether an option is worth
showing: a weak programme's own range is ~105,000 ranks wide, so it would
qualify as Safe at every rank. Without a floor a rank-100 student was offered
1,576 "Safe" options running out to cut-off 262,158, each labelled 100%. KCET
therefore cuts at `relevance_ceiling_z = 4.0` on a **separate** relevance sigma,
and tops the list back up to `min_options = 25` from the held-back near-certain
options when the window is tighter than a usable list.

COMEDK has no equivalent: its modelled bands are narrow enough that bucketing
alone does the job.

### 4.4 Scoring, confidence and explanations

| Axis | KCET | COMEDK |
|---|---|---|
| Quality score | `10 × percentile` within `seat_category`, **ordinal** ties. Competitive demand carries the whole score — no brand signal exists to blend in. | `10 × (0.70 × percentile within quota + 0.30 × brand_score)`, **dense** ties. |
| Tie rule, why | A single category holds thousands of rows; sharing a percentile would compress the scale where the data is densest. | Ties are common over a narrow range; two programmes closing at the same rank should not be ordered against each other by this key. |
| Brand signal | None. | Institute tier derived from **median GM cut-off** (elite/top/strong/mid/emerging). Only five values, so it is a mild prior, not the primary key. |
| `confidence` | **Two** values: `high` at \|z\| ≥ 1.5, else `medium`. | **Three**: adds `borderline` at \|z\| < 0.5 (a coin flip). |
| Reason text | One sentence + a headroom tail; names the seat category when it is not GM. | One or two clauses + a headroom tail; names the brand tier and the KKR gap. |
| Languages | English only. | `en` / `hi` / `gu` / `kn` for guidance, notes, fit labels and reasons. |

Both derive the confidence label from the **same z-score** that produces the
percentage, so a card can never show a label that disagrees with its own number.
The label vocabularies stay per-exam because they answer different questions —
a shared enum would force one of them to lie.

### 4.5 Top-rank mode

|  | KCET | COMEDK |
|---|---|---|
| Trigger | Bucket counts alone (Target and Reach both empty). | Bucket counts **and** a hard gate: rank ≤ 100. |
| Shortlist size | 25 | 10 |
| Against a single-bucket request | **Loses** — the request is honoured and the bucket's own ordered list is returned. | **Wins** — the top-rank shortlist is built first, then the bucket filter runs over it. |

The trigger is deliberately not a hardcoded rank in either exam: the rank scale
differs wildly per category, so counts are the only signal that adapts.

How much that precedence difference actually shows, checked against the shipped
datasets rather than assumed:

* **COMEDK, visibly.** `rank 50, quota GM, bucket=safe` returns **10** cards
  (the top-rank cap) out of **832** eligible Safe options. Without the
  precedence it would return all 832, paginated.
* **KCET, not currently.** Every top-rank case in the 2025 data has exactly 25
  eligible Safe options, because the relevance window plus the `min_options`
  top-up produces 25 — the same number as `top_rank_cap`. The two branches
  therefore agree today. The difference is real in the code and would surface
  the moment either constant moved, which is why it is written down rather than
  quietly relied upon.

### 4.6 Curation and paging

| Axis | KCET | COMEDK |
|---|---|---|
| Default caps (Target/Reach/Safe) | 25 / 15 / 15 | 30 / 20 / 25 |
| Max per institute | 2 | 2 |
| Single-bucket request | Returns that bucket sliced to `max_results` (default 5,000). | Returns that bucket **uncapped**, then paginates (`page`, `page_size`, default 50). |
| Pagination | None. | Yes, with `has_next`. |

Neither exam ever deletes an eligible option: capping only bounds what the
default response *displays*, and every eligible programme stays counted and
reachable through the per-bucket view.

### 4.7 Edge-case messaging

| Case | KCET | COMEDK |
|---|---|---|
| Implausible rank | Adds a note; still recommends. | Returns immediately with zeroed counts and a "check your result card" message. |
| Rank past all data | "past the last seat you are eligible for … the weakest cutoff closed at N". | Two variants — options still shown (speculative) vs none at all. |
| Everything clears | Covered by top-rank mode. | Extra `all_safe` note. |
| No safe backup | — | Extra `no_safe` note. |
| Quota caveat | — | KKR note: a KKR seat is not automatically easier. |

Response shapes differ too — COMEDK keeps legacy `safe`/`target`/`reach` lists
and `has_next` for its frontend; KCET does not. [docs/API.md](API.md) is the
authoritative per-exam contract.

---

## 5. Where to make a change

| You want to change… | Edit | Affects |
|---|---|---|
| What "Target" means, ordering, capping, top-rank detection, the probability curve | `app/disha/core/` | **Every exam** — re-run the golden suite |
| Which round a rank is compared against, how a CSV cell is parsed | `app/disha/core/rounds.py` | **Every point-cutoff exam** |
| A band width, sigma, cap, or typo guard for one exam | `app/disha/<exam>/config.py` | That exam only |
| Eligibility, seat categories, quotas, branch classification | `app/disha/<exam>/states.py` + that exam's `data_loader.py` | That exam only |
| Note wording, guidance, languages, response fields | `app/disha/<exam>/recommender.py`, `schemas.py` | That exam only — update [docs/API.md](API.md) |

Any change that alters an API response will fail the golden suite
([tests/golden/README.md](../tests/golden/README.md)). That is the point:
re-capture it in its own commit so the diff is a reviewable record of what
changed, never folded into a refactor.
