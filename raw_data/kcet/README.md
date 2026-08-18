# KCET (UGCET) 2025 — raw source status

**Engineering only.** All rounds collected from KEA's official site. Nothing missing.

> **Compiled output:** `app/disha/kcet/data/kcet_2025_all_rounds.csv` (55,932
> rows) is built from the six final-round PDFs below by
> `scripts/build_kcet_dataset.py`, and **is the file the KCET engine reads**.
> **[docs/DATA_PIPELINE.md](../../docs/DATA_PIPELINE.md) is the runbook** — how to
> source next year's documents, which to use and which to skip, how to rebuild,
> and how to verify the result. This file only records what was downloaded.

## Where these came from

KEA's main portal has rolled over to 2026, so the 2025 documents are no longer
linked from the landing page. They are still published at the year-specific page:

- Index page: https://cetonline.karnataka.gov.in/kea/ugcet2025.aspx
- File host: `https://cetonline.karnataka.gov.in/keawebentry456/ugcet2025/`

KEA names these files `PROF_CODE_<course>_<region>_<round>kannada.pdf`, where
`E` = Engineering, `R` = Rest of Karnataka, `H` = 371(j) Kalyana-Karnataka.
Despite the `kannada` filename suffix, the documents are in English.

**Every round is split into two documents by seat type.** Both are needed for a
complete picture — merging only one half silently drops a whole quota:

- `_rok` = *Rest of Karnataka* cut-off ranks
- `_hk` = *371(j) Kalyana-Karnataka* cut-off ranks

## Files

| File | Round | Seat type | Colleges | KEA source name |
|---|---|---|---|---|
| `kcet_mock_rok.pdf` | Mock | Rest of Karnataka | 227 | `PROF_CODE_e_Rkannada.pdf` |
| `kcet_mock_hk.pdf` | Mock | Kalyana-Karnataka | 227 | `PROF_CODE_e_hkannada.pdf` |
| `kcet_round1_provisional_rok.pdf` | R1 provisional (Aug 1) | Rest of Karnataka | 227 | `PROF_CODE_E_R_01082025kannada.pdf` |
| `kcet_round1_provisional_hk.pdf` | R1 provisional (Aug 1) | Kalyana-Karnataka | 227 | `PROF_CODE_E_H_01082025kannada.pdf` |
| `kcet_round1_rok.pdf` | **R1 final (Aug 2)** | Rest of Karnataka | 224 | `PROF_CODE_E_R_R1kannada.pdf` |
| `kcet_round1_hk.pdf` | **R1 final (Aug 2)** | Kalyana-Karnataka | 224 | `PROF_CODE_E_H_R1kannada.pdf` |
| `kcet_round2_provisional_rok.pdf` | R2 provisional | Rest of Karnataka | 228 | `PROF_CODE_E_R_R2kannada.pdf` |
| `kcet_round2_provisional_hk.pdf` | R2 provisional | Kalyana-Karnataka | 228 | `PROF_CODE_E_H_R2kannada.pdf` |
| `kcet_round2_rok.pdf` | **R2 final (Aug 30)** | Rest of Karnataka | 228 | `PROF_CODE_E_R_30082025kannada.pdf` |
| `kcet_round2_hk.pdf` | **R2 final (Aug 30)** | Kalyana-Karnataka | 228 | `PROF_CODE_E_H_30082025kannada.pdf` |
| `kcet_round3_rok.pdf` | **R3 final (Sep 11)** | Rest of Karnataka | 229 | `PROF_CODE_E_R_11092025kannada.pdf` |
| `kcet_round3_hk.pdf` | **R3 final (Sep 11)** | Kalyana-Karnataka | 229 | `PROF_CODE_E_H_11092025kannada.pdf` |

Round identity was read from each PDF's own header line
(`UGCET-2025 ... CUT-OFF RANKS FOR Engineering` + `Seat Type:`), not inferred
from the filename. Round 3 has no separate provisional cut-off document —
only a notice PDF, which is not data and was not collected.

### Supplementary (for validating college/branch coverage)

| File | Contents |
|---|---|
| `kcet_engg_additional_seat_matrix.pdf` | Engineering additional seat matrix, 06-09-2025 |
| `kcet_engg_vacancy_after_all_rounds.pdf` | Engineering allotment/vacancy after all rounds |

### Superseded

| File | Note |
|---|---|
| `kcet_round1.csv` | Copy of `app/disha/kcet/data/kcet_2025.csv`. **Do not re-use — corrupted.** Kept only for diffing against a clean re-parse. |

### Which of these feed the compiled dataset

Only the **six final-round PDFs** (R1/R2/R3 × RoK/HK). Mock, both provisional
pairs, the seat-matrix letter, the vacancy statistics and the old CSV are all
excluded — each for a different reason, documented with the supporting diffs in
[docs/DATA_PIPELINE.md §1](../../docs/DATA_PIPELINE.md#which-documents-to-use).
The short version:

- **Round 1 provisional → final is a real revision** (128 RoK rows and 33 HK rows
  changed, 3 colleges dropped), so the provisional is genuinely superseded.
- **Round 2 provisional → final is not** — the only differences are the
  `Generated on:` footer and one added row. It is a same-day reprint.
- **Mock allotted no seats**, so its cut-offs describe an allotment that never
  happened.
- **`kcet_engg_additional_seat_matrix.pdf` is not a seat matrix** — it is a
  one-page scan of a letter sanctioning a single 60-seat programme.

## Why `kcet_round1.csv` must be replaced

`kcet_round1_rok.pdf` contains **224 colleges** — exactly matching the 224
distinct `college_code` values in the existing CSV. That confirms the CSV was
derived from the Round 1 final Rest-of-Karnataka document.

The PDFs also explain the `course_name` corruption found in the audit. Course
names wrap across several physical lines in the source table:

```
Course Name        1G      1K      1R     2AG   ...
ARTIFICIAL        7516     --      --     6634
INTELLIGENCE AND
DATA SCIENCE
CIVIL            70257     --    89409   63957
ENGINEERING
```

The original extraction kept only the first line of each wrapped name and let
the remaining lines collide with the next row's first line. That is precisely
how `ARTIFICIAL`, `ENGINEERING COMPUTER` and
`INTELLIGENCE AND DATA SCIENCE CIVIL` ended up in the CSV.

**A correct re-parse must join the wrapped continuation lines before splitting
rows.** The rank columns are the reliable anchor: a row's numbers all sit on the
first physical line, and any following line without numbers is a continuation of
the course name above it.

Two further things the existing CSV misses, both of which the raw PDFs contain:

1. **The `_hk` half was never imported.** The CSV has only Rest-of-Karnataka
   ranks; all 371(j) Kalyana-Karnataka cut-offs are absent.
2. **Ranks can be fractional.** Values such as `76553.5` and `19245.75` appear
   throughout. Parsing these as `int` truncates them — the current loader's
   `_safe_int` does exactly that.

### Status: the clean re-parse now exists

`scripts/build_kcet_dataset.py` produces `kcet_2025_compiled.csv`, and it was
diffed against `kcet_round1.csv`: same 18,850 rows, same 224 colleges, and all
**4,543** `(college, category)` rank multisets identical, with 224 corrupted
course names collapsing to 140 clean ones. So this file's numbers were always
right — only the names were destroyed.

Two corrections to the guidance above, learned while writing that parser:

- Joining "any following line without numbers" is **not** sufficient. A
  continuation line can carry a digit: a rank too wide for its cell overflows
  onto the next line, so `15223.875` renders as `15223.87` plus a bare `5`
  below it. Ranks carry up to *three* decimals, so the truncated half does not
  reliably end in `.` either.
- The rank columns are a reliable anchor only via **coordinates**, not text
  layout. See [docs/DATA_PIPELINE.md §5](../../docs/DATA_PIPELINE.md#5-why-the-parser-reads-coordinates-not-text).

The compiled CSV **is now the KCET engine's data source**, replacing
`app/disha/kcet/data/kcet_2025.csv`. What that required in the engine, and what
it changed, is in
[docs/DATA_PIPELINE.md §6](../../docs/DATA_PIPELINE.md#6-adoption-status-done).

## Scope

Engineering only, per current scope. Architecture (`PROF_CODE_A_*`) exists on the
same KEA page and follows the identical naming scheme if it is ever needed.
