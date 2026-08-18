# Cutoff data pipeline

How raw cut-off documents become the CSVs the engines read. Written for the
person doing next year's refresh, who will not have been part of the 2025 work.

Everything here was verified against the 2025 documents and the parser output;
where a claim is unverified it says so. If you change the pipeline, update this
file in the same change — see [CONTRIBUTING.md](../CONTRIBUTING.md).

| Exam | Raw sources | Build script | Compiled output | Wired into the app? |
|---|---|---|---|---|
| KCET | `raw_data/kcet/` (14 PDFs) | `scripts/build_kcet_dataset.py` | `app/disha/kcet/data/kcet_2025_all_rounds.csv` | **Yes** — see [§6](#6-adoption-status-done) |
| COMEDK | `raw_data/comedk/` (6 PDFs) | `scripts/build_comedk_dataset.py` | `app/disha/comedk/data/comedk_2025_all_rounds.csv` | **Yes** — see [§7](#7-comedk--building-the-csv) |
| JEE | *(none — CSV was sourced pre-pipeline)* | *(none)* | — | `app/disha/data/josaa_merged_2025.csv` |

KCET and COMEDK both have end-to-end reproducible pipelines. JEE still ships a
CSV whose provenance is not reproducible from this repo; rebuilding it the same
way is unfinished work, not a decision that it should stay manual.

---

## 1. KCET — getting the raw documents

### Where they live

KEA publishes engineering cut-offs as PDFs on a **year-specific** page. The main
portal rolls over each year and stops linking the previous year, but the old
year-page keeps working:

- Index page: `https://cetonline.karnataka.gov.in/kea/ugcet<YEAR>.aspx`
- File host: `https://cetonline.karnataka.gov.in/keawebentry456/ugcet<YEAR>/`

For 2026, start at `ugcet2026.aspx`. Do not assume the file-host path stays
`keawebentry456` — that segment has no documented meaning and could change.
Open the index page and read the real link targets.

### Naming scheme

Files are named `PROF_CODE_<course>_<region>_<round>kannada.pdf`:

| Token | Meaning |
|---|---|
| `<course>` | `E` = Engineering, `A` = Architecture |
| `<region>` | `R` = Rest of Karnataka, `H` = 371(j) Kalyana-Karnataka |
| `<round>` | `R1`, `R2`, or a date like `30082025` |

The `kannada` suffix is misleading — the documents are in English.

**Every round is split into two documents by region.** Downloading only one half
silently drops an entire quota; that is exactly how the 2025 dataset shipped
with no Kalyana-Karnataka data at all. Always take both.

Rename on download to the flat convention this repo uses
(`kcet_round1_rok.pdf`, `kcet_round1_hk.pdf`, …) and record the original KEA
filename in `raw_data/kcet/README.md`, so a future reader can find the source
again after KEA reorganises.

### Which documents to use

This was decided by diffing the 2025 documents, not by reading their titles.

**Use — these six feed the compiled dataset:**

| File | Why |
|---|---|
| `kcet_round1_rok.pdf` / `_hk.pdf` | Round 1 final, after objections |
| `kcet_round2_rok.pdf` / `_hk.pdf` | Round 2 final |
| `kcet_round3_rok.pdf` / `_hk.pdf` | Round 3 final — the last round |

**Exclude:**

| File | Why |
|---|---|
| `kcet_mock_*.pdf` | Mock allotment is a trial run on preliminary option entries. No seats are allotted and candidates then revise their options, so the numbers describe an allotment that never happened. |
| `kcet_round1_provisional_*.pdf` | Genuinely superseded. The final revised **128** RoK rows and 33 HK rows and dropped three colleges. Keep the files only if you want to measure how far objections move ranks. |
| `kcet_round2_provisional_*.pdf` | Not a draft at all — a same-day reprint. The only differences from the final are the `Generated on:` footer (13:30 vs 17:04 on 30-08-2025) and one added course row. Carries no information. |
| `kcet_engg_additional_seat_matrix.pdf` | **Not a seat matrix.** A one-page scanned image (no extractable text) of a government letter sanctioning a single programme — B.Tech Mechanical at VTU CPGS Kalaburagi, intake 60. Reference only; not parseable without OCR and not worth OCRing for one row. |
| `kcet_engg_vacancy_after_all_rounds.pdf` | Real, parseable data (192 colleges, 14,940 vacant seats) but a different shape: leftover seats, **not** total intake, so fill rate cannot be derived from it alone. Belongs in a separate vacancy table if it is ever needed. |
| `kcet_round1.csv` | The old corrupted extract. Superseded — see [§4](#4-verifying-a-rebuild). |

**Rule of thumb for a new year:** take the *final* document of every round that
actually allotted seats. Verify provisional-vs-final by diffing rather than
assuming — in 2025 the answer differed between Round 1 and Round 2.

### Is a seat matrix needed?

Not for the KCET engine as it stands. `PointCutoffModel`
([`app/disha/core/cutoff.py`](../app/disha/core/cutoff.py)) computes admission
probability as a logistic on rank-distance from the cut-off; seat counts never
enter it.

A seat matrix becomes worth fetching only if someone builds a supply-aware
feature — "X of N seats filled", or probability from fill rate. That needs the
*full original* intake matrix, which combined with the vacancy PDF above gives
`fill_rate = (intake − vacant) / intake`.

COMEDK's seat matrix **is** now parsed and joined into its CSV ([§7](#7-comedk--building-the-csv)),
which is what makes that dataset's vacancy rows possible. No engine reads the
seat columns yet — they are carried, not consumed.

---

## 2. KCET — building the CSV

```bash
pip install pdfplumber                       # build-time only; not in requirements.txt
python3 scripts/build_kcet_dataset.py        # writes app/disha/kcet/data/kcet_2025_all_rounds.csv
```

Useful flags:

| Flag | Effect |
|---|---|
| `--report-only` | Parse and validate, write nothing. Use this first. |
| `--out PATH` | Write somewhere else. |
| `--keep-non-engineering` | Retain the architecture/design/planning programmes normally filtered out. |

A full run reads ~611 pages and takes roughly **4 minutes**. It prints a
per-file summary and aborts if any document fails its header check.

`pdfplumber` is deliberately **not** in `requirements.txt`: the app reads the
generated CSV and never opens a PDF, so it is not a runtime dependency.

### Output schema

`app/disha/kcet/data/kcet_2025_all_rounds.csv` — **one row per programme**
(college x course x category), with **a column per round**. 24,495 rows for
2025, carrying all 55,932 published cut-offs.

| Column | Notes |
|---|---|
| `exam_type` | `KCET` |
| `year` | `2025` |
| `seat_type` | `ROK` (Rest of Karnataka) or `HK` (371(j) Kalyana-Karnataka) |
| `college_code` | `E001`-style KEA code |
| `college_name` | Verbatim from the PDF |
| `course_name` | Wrapped lines rejoined; see [§5](#5-why-the-parser-reads-coordinates-not-text) |
| `category` | Published category code — **disjoint vocabularies per seat type** |
| `closing_rank_r1` | Round-1 cut-off. May be fractional, up to three decimals |
| `closing_rank_r2` | Round-2 cut-off |
| `closing_rank_r3` | Round-3 cut-off |

```
exam_type,year,seat_type,college_code,college_name,course_name,category,closing_rank_r1,closing_rank_r2,closing_rank_r3
KCET,2025,ROK,E001,"Univesity of Visvesvaraya …",ARTIFICIAL INTELLIGENCE AND DATA SCIENCE,GM,4628,6389,7213
```

**A blank round cell is meaningful**: the programme allotted no seat that round,
so KEA published no cut-off for it. It is not missing data. 2025 fill rates:
24,046 / 18,287 / 13,599 of 24,495 for rounds 1 / 2 / 3 — the coverage cliff
behind the default in [§6](#6-adoption-status-done). Cells printed `--` in the
PDF mean the same thing and become blanks here.

**Wide on rounds, long on category** — the two axes are not alike:

* *Rounds* are a safe axis to widen on. There are three, the set is fixed for a
  year, and one row then shows a programme's whole history at a glance instead
  of forcing a grep across three rows.
* *Category* stays a row value. That set **changes between rounds** — 24 codes
  in round 1, 28 in rounds 2-3 (`GMP`, `NRI`, `OPN`, `OTH` appear later) — so
  category columns would need a per-round map and would be mostly empty.

The build script derives the round columns from the rounds it actually parsed,
and the loader discovers them from the CSV header (`closing_rank_r<N>`), so a
year with four rounds needs no code change in either — only new `SOURCES`
entries.

**RoK and HK share one table with a `seat_type` column** rather than living in
two files. They have identical structure and are quota slices of the same
allotment — a student is eligible for exactly one — so selecting between them is
a `WHERE` clause, not a different entity. It also makes the 2025 bug
structurally impossible to repeat: a missing partition in one table is visible
in any `GROUP BY`, whereas a missing second file is invisible.

### Category codes

HK does **not** reuse the RoK codes. It uses a parallel set with an `H` suffix:

| RoK | `1G` `1K` `1R` `2AG` … `GM` `GMK` `GMR` `SCG` … `STR` | 24, plus `GMP` `NRI` `OPN` `OTH` in R2/R3 |
|---|---|---|
| **HK** | `1H` `1KH` `1RH` `2AH` … `GMH` `GMKH` `GMRH` `SCH` … `STRH` | 24, plus `GMPH` in R2/R3 |

Five of the 53 possible codes never carry a value anywhere in the 2025 data
(`GMP`, `NRI`, `OPN`, `OTH`, `GMPH` — every cell is `--`), so the compiled CSV
contains 48 distinct categories. That is expected, not data loss.

---

## 3. Refreshing for a new year

Everything year-specific in `scripts/build_kcet_dataset.py` sits in two places.

1. **Download the new PDFs** into `raw_data/kcet/` following §1, and update
   `raw_data/kcet/README.md` with the KEA source filenames.

2. **Update `YEAR`** (top of the script).

3. **Update the `SOURCES` table.** One entry per document:

   ```python
   Source("kcet_round1_rok.pdf", 1, "ROK",
          "UGCET-2025 ALLOTMENT CUT-OFF RANKS",   # title_fragment
          "Rest Of karnataka",                     # seat_fragment
          224)                                     # expected_colleges
   ```

   - `title_fragment` and `seat_fragment` are **asserted against the PDF's own
     first page**; the run aborts on a mismatch. This is deliberate — it stops a
     mislabelled download from silently entering the dataset under the wrong
     round. KEA is inconsistent about these strings (`ALLOTMENT CUT-OFF RANKS`
     for R1, `SESSION-2 ALLOTMENT CUT-OFF RANKS` for R2, `THIRD ROUND CUT-OFF
     RANKS` for R3), so read them off the new documents rather than guessing.
   - `expected_colleges` only warns on mismatch. Get it from the round's own
     document, then confirm the drift between rounds is explainable — colleges
     legitimately join mid-counselling.

4. **Add rounds if the count changed.** The parser does not assume three rounds.

5. **Re-run with `--report-only`** and work through [§4](#4-verifying-a-rebuild).

6. **Decide the filename.** `kcet_2025_all_rounds.csv` is year-stamped. Point
   `Settings.csv_path` in `app/disha/kcet/config.py` at the new file and update
   `DATA_FILES` in `tests/golden/matrix.py`, then re-capture the goldens.

7. **Round columns need no code change.** The build script emits one
   `closing_rank_r<N>` column per round it parsed, and the loader discovers them
   from the header. A year with four rounds just produces a fourth column.

---

## 4. Verifying a rebuild

The script self-checks and exits non-zero on a validation failure, but a clean
exit is not sufficient. Also confirm:

- [ ] **College counts match the source documents** per round and seat type.
      2025: 224 / 224 / 228 / 228 / 229 / 229.
- [ ] **`off-grid values` is 0.** Anything else means a value did not land within
      tolerance of a category column — the layout changed and the column model
      needs revisiting.
- [ ] **No row has an implausibly small rank.** A rank below ~100 is the
      signature of an overflow fragment being read as a whole value; see §5.
- [ ] **Distinct course names is in the low hundreds, not ~one per college.**
      2025: 142. A number close to the college count means wrapped names are not
      being rejoined and each college has its own mangled variants.
- [ ] **Row count equals the programme count, not the cut-off count.** The file
      is pivoted to one row per programme; 2025: 24,495 rows holding 55,932
      cut-offs. A row count near the cut-off count means the pivot did not run.
- [ ] **Every row has at least one non-blank round column.** A programme with no
      cut-off in any round should not exist; `validate_wide` fails the build on
      this.
- [ ] **No despaced-key collisions remain** — two course names identical once
      whitespace is stripped mean a word is being split inconsistently.
- [ ] **Dropped programmes are all genuinely non-engineering.** The run prints
      each one; 2025 dropped 8 cells across `DESIGN`, `PLANNING`, `B.Plan` and
      `BACHELOR OF DESIGN`.

### Diffing against the previous extract

For 2025 the new parse was checked against the old `kcet_round1.csv`:

| | old | new (R1/RoK) |
|---|---|---|
| rows | 18,850 | 18,850 |
| colleges | 224 | 224 |
| `(college, category)` rank multisets | 4,543 | **4,543 identical (100%)** |
| ranks present in old but missing from new | — | 0 |
| distinct course names | 224 | 140 |

The conclusion worth carrying forward: **the old extract's numbers were always
correct — only the course names were destroyed.** So when validating a new
parser against an old one, compare rank multisets grouped by
`(college_code, category)`, not whole rows; course names are the thing most
likely to differ legitimately.

`kcet_round1.csv` exists only to make that diff reproducible. Once a rebuild is
validated and adopted it can be deleted; leaving a plausible-looking but
corrupted CSV in `raw_data/` invites someone to load it.

---

## 5. Why the parser reads coordinates, not text

If you rewrite this, do not start from `pdftotext`. Three traps, all of which
the 2025 extract fell into:

**1. Course names wrap across physical lines.**

```
Course Name        1G      1K      2AG
ARTIFICIAL        7516     --     6634
INTELLIGENCE AND
DATA SCIENCE
CIVIL            70257     --    63957
ENGINEERING
```

Keeping only the first line produces the course `ARTIFICIAL` and lets the
remainder collide with the next row — which is how `ENGINEERING COMPUTER` and
`INTELLIGENCE AND DATA SCIENCE CIVIL` ended up in the old CSV as course names.

**2. Cut-offs too wide for their cell overflow onto the next line.** A rank of
`15223.875` renders as `15223.87` on the data line with a bare `5` on the line
below, positioned under the same column. A line parser reads `15223.87` and then
treats the `5` as a new row — creating a phantom course whose only cut-off is
`5`. Note the trap within the trap: ranks carry **up to three decimals**, so the
truncated half does not necessarily end in `.`, and testing for a trailing dot
misses these entirely.

**3. The same course splits differently in different rounds.** The name column
is narrower in Rounds 2 and 3 (28 categories, not 24), so `INTERNET` wraps as
`INTERNE` + `T` there but not in Round 1 — one course, two names.

### How the parser handles each

- **Columns** come from each document's own `Course Name | 1G | 1K | …` header
  row; every value is horizontally centred on its category header, so values are
  assigned to the nearest header centre. This is what absorbs the 24-vs-28
  category difference without a hardcoded column map.
- **Course names** are whatever sits left of the first category column. A line
  with no values is a continuation of the name above it.
- **Overflow tails** are detected by *value count*, not by a trailing dot: KEA
  renders every cell including `--`, so a real row carries one value word per
  column while an overflow tail carries one or two bare digit-runs.
- **Inconsistent splits** are folded by grouping names that agree once
  whitespace is removed and keeping the variant with the fewest tokens — a
  mid-word split always adds a token. Eight 2025 names split identically in
  every round (always a lone letter stranded after `(`, e.g.
  `ENGINEERING(D ATA SCIENCE)`), so no unsplit variant existed to fold onto;
  a narrow rule repairs that one pattern. It is not cosmetic:
  `(D ATA SCIENCE)` does not contain the token `DATA`, so
  `classify_kcet_branch` tags it `cse` and misses `ai_ds`.

Geometry cannot solve everything. A wrap at a space and a wrap mid-word are
indistinguishable by coordinates alone — both end at the column edge — which is
why the fold above is arithmetic on tokens rather than more geometry.

### KEA's own errors are preserved verbatim

The source documents contain misspellings, and the parser does not correct them:
`Univesity` (E001), `Achitecture` (E225), `ARTIFICAL`, `MATHAMATICS`, `SICENCE`.
Leave them alone. `classify_kcet_branch` is keyword-bag based specifically
because this vocabulary is unreliable, and "fixing" spellings in the data
creates a silent mismatch with anything keyed on the published name.

---

## 6. Adoption status (done)

The KCET engine reads the compiled dataset. The build script writes it straight
to `app/disha/kcet/data/kcet_2025_all_rounds.csv`, which is the runtime file, so
a rebuild lands where it is used.

What changed in the engine when it was adopted:

1. **371(j) category codes are understood.**
   [`states.py`](../app/disha/kcet/states.py) gained `split_seat_pool()` and
   `is_kalyana_karnataka()`, reducing an HK code to its Rest-of-Karnataka
   equivalent for labelling and prefixing the label `371(j) — `. Previously all
   24 HK codes would have rendered as their raw code with a wrong region label.

2. **Cut-off = MAX across rounds 1-3 by default**, in
   [`data_loader.py`](../app/disha/kcet/data_loader.py). The old loader kept the
   *first* row per `(college, course, category)`, which on a multi-round file
   would silently have meant "round 1 only".

   The round-wise record is **not** collapsed away. `_load_raw_rows` groups
   every published round per programme; `_resolve_rank` picks the one number the
   recommender compares against; and each `KcetProgram` keeps its full history
   in `closing_rank_by_round`. Choosing a round is therefore a code-level
   decision, not something baked into the dataset:

   ```python
   load_programs()          # settings.round_strategy — "max" by default
   load_programs("last")    # the last round each programme appears in
   load_programs("first")
   load_programs(1)         # round 1 only
   program.rank_in_round(2) # this programme's round-2 cut-off, or None
   ```

   `max`, `last` and `first` all resolve for any programme, so each covers the
   full 24,495. A fixed round number is a strict subset by design — 24,046 /
   18,287 / 13,599 for rounds 1 / 2 / 3 — because a programme that allotted no
   seat in a round has no cut-off for it and must drop out rather than borrow a
   neighbouring round's number. That coverage cliff is why `max` is the default
   rather than "the final round". `quality_score` is recomputed per strategy,
   since it is a percentile of the ranks actually selected.

   Covered by `tests/test_kcet_rounds.py`; the golden suite only exercises the
   default.

3. **Ranks are floats end to end.** `_safe_float` replaced `_safe_int`, and
   `KcetRecommendation.closing_rank` is `float` in
   [`schemas.py`](../app/disha/kcet/schemas.py) — declaring it `int` made
   pydantic reject every programme with a fractional cut-off.

The 63 KCET golden cases were re-captured; JEE and COMEDK were unaffected.

### Known consequence, not yet addressed

The band constants in [`kcet/config.py`](../app/disha/kcet/config.py) were
measured against the round-1 distribution. Taking the maximum across rounds
barely moves the tail the ceilings were scaled from (GM max 249,733 → 262,158,
+5%) but roughly doubles the middle (GM median 67,328 → 128,953). The bands are
absolute, so proportionally more programmes now land in **Safe** and the
Safe/Target/Reach split discriminates less than it did. Re-tuning is a product
decision that belongs in its own change; the constants were deliberately left
untouched here so the data swap stays attributable. The numbers to tune against
are in that file's docstring.

### Still open

- ~~The `K` suffix on Rest-of-Karnataka codes is probably mislabelled.~~
  **Resolved.** `K` and `R` are KEA's Kannada-medium and rural sub-quotas;
  Kalyana-Karnataka is the separate 371(j) *pool* axis. Labels updated in
  `states.py` and in the KCET frontend, which now asks category × sub-quota ×
  pool as three questions and composes the code. See
  [docs/API.md](API.md#kcet-endpoints).
- **`stats_loader.py` still truncates** cut-offs with `int()` in its top-10
  tables. Harmless for a leaderboard display, but inconsistent with the rest of
  the engine now that ranks are floats.
- **`kcet_2025.csv`** (the superseded round-1 extract) is still in the package
  data directory. It is no longer read; delete it once nobody needs the diff.

---

## 7. COMEDK — building the CSV

```bash
python3 scripts/build_comedk_dataset.py                 # write the CSV
python3 scripts/build_comedk_dataset.py --report-only    # parse + validate, write nothing
```

Same shape as the KCET builder: `pdfplumber`, word coordinates, one row per
programme with a column per round. Reads the six PDFs in `raw_data/comedk/` and
writes `app/disha/comedk/data/comedk_2025_all_rounds.csv`.

### What the source documents are

| File | Role | Categories |
|---|---|---|
| `comedk_seat_matrix.pdf` | Seats + fees, published before round 1 | GM + HKR |
| `comedk_mock.pdf` | Mock allotment, 22.07.2025 — a simulation | GM + KKR |
| `comedk_round1.pdf` | Round 1, 28.07.2025 | GM + KKR |
| `comedk_round2.pdf` | Round 2, 12.08.2025 | **KKR only** |
| `comedk_round3.pdf` | Round 3, 22.08.2025 | **GM only** |
| `comedk_round4_final.pdf` | Round 4 final, 05.09.2025 | **GM only** |

COMEDK ran round 2 as a Kalyana-Karnataka-only mop-up and rounds 3–4 as
general-merit rounds. **A KKR cut-off for round 3 does not exist, and a GM
cut-off for round 2 does not exist.** Those are empty cells in the output and
they are facts, not gaps to interpolate. The builder asserts each document's
category set and fails the build if one drifts.

### Output schema

```
exam_type,year,college_code,college_name,course_code,course_name,category,
total_seats,category_seats,tuition_fee,other_fee,total_fee,
closing_rank_mock,closing_rank_r1,closing_rank_r2,closing_rank_r3,closing_rank_r4
```

2,131 rows — 150 colleges × 69 courses × the categories each offers.

Two schema decisions worth knowing:

- **`closing_rank_mock` is not `closing_rank_r0`.** The runtime loader
  discovers rounds with `^closing_rank_r(\d+)$`, so this name keeps a
  simulation that allotted no seat out of every round strategy. It is carried
  as a demand signal and exposed as `mock_rank`.
- **1,005 rows have no cut-off in any round.** They had seats and never filled.
  They carry seats and fees with every rank column blank — the vacancy signal,
  visible only because the seat matrix is joined in. `data_loader` skips them
  (nothing to compare a rank against) and logs the count.

Unlike KCET there is no `seat_type` column: COMEDK's two categories *are* its
two pools, and the codes are disjoint, so `category` identifies its own pool.

### Why the parser reads coordinates, not text

The five cut-off PDFs are **wide pivot grids**, not row-per-cut-off tables:
rows are (college, category), columns are the 68 courses, and a blank cell means
no seat was allotted. 68 columns do not fit a letter page, so each sheet prints
in horizontal **blocks** that repeat the whole college list with the next group
of columns — round 1 is 10 blocks × 16 pages. The builder detects a block where
the college list restarts, which is the only signal holding across all five
(pages-per-block is 16 / 7 / 8 / 5 / 11).

A text-layer parser gets all of the following wrong, and each was observed:

- **Course codes are 2, 3 or 4 letters** — `AVE BDC BFD BID BLD CAD CBD CCA CCS
  CIT CSB CSD ECE ECV IAR IDA INT IST MAE ROB VLS` alongside `CS`/`CV`. A
  `[A-Z]{2}` reading maps `CAD-Computer…` onto `CA`, a different course in an
  adjacent column. This single bug made 99 round-1 pairs look absent from the
  seat matrix when the true number is 1.
- **Two codes have a space before the hyphen** (`IDA -Information Technology`,
  `IAR - Virtual Reality`), so code and hyphen are separate words. These two
  rows are 30 of the 26,827 seats.
- **Near-duplicate codes sit in neighbouring columns** — `RI`/`ROB`, `VL`/`VLS`,
  `CI`/`CIT`, `CA`/`CAD`. A 40pt column error writes a robotics rank into the
  VLSI row and looks entirely plausible.
- **Rows wrap.** 89 seat-matrix rows put the college code on a different
  physical line from its numbers.
- **Row pitch is not constant** — 18.6pt in round 1, 9.6pt in the mock, 10.4pt
  in round 4. It is measured per document.
- **`Page N of M` renders `M` at x=415**, inside the data area. The footer is
  dropped explicitly rather than relying on it sitting clear of the last row.
- **One college is named "GM Institute of Technology"** (E051, Davangere), so
  scanning text for `GM` to find the category column matches that college's
  *name* on every one of its rows.
- **The seat matrix header says `HKR` where the cut-off files say `KKR`** —
  while its own footnote defines the code as KKR. Same category. Joining on the
  raw string silently drops every KKR row.

### Verifying a rebuild

The build refuses to write unless all of these hold:

1. Each document's own title line names the round it is claimed to be.
2. Each document publishes exactly the categories the source table expects.
3. No **column collision** — two ranks landing on one (college, course,
   category) key means two columns resolved to the same code, so a rank would be
   attributed to the wrong course. Currently zero across all five documents.
4. `closing_rank_r2` is KKR-only; `r3` and `r4` are GM-only.
5. The parsed seat matrix reconciles to **COMEDK's own printed grand total** on
   page 52: `26,827 = 22,813 GM + 4,014 KKR`, and `Total = GM + KKR` on every
   one of the 1,067 rows.

Check 5 is the one that catches a dropped or double-counted row, which nothing
structural would notice. It is why the seat matrix is worth parsing even though
no engine reads the seat columns yet.

### What this replaced

`comedk_2025.csv` — 637 rows, one `Closing_R1` column — did not survive being
checked against the official documents:

- its `Opening_R1` was a verbatim copy of `Closing_R1` on all 637 rows;
- 48% of its closing ranks appear **nowhere** in any of the five cut-off PDFs
  for the matching college and quota, and the values that do match are spread
  across rounds 1–4 *and* the mock — so it was not a snapshot of any one round;
- it covered 101 of 150 colleges and 46 of 69 courses.

It is still in the package data directory and is no longer read; delete it once
nobody needs the diff.

### Known consequence, not yet addressed

The band constants in [`comedk/config.py`](../app/disha/comedk/config.py) were
measured against the old round-1-only distribution. The rank *scale* is
unchanged (max still 111,800, min still 692), so the ceilings still sit where
they were measured. But the dataset grew 637 → 1,114 rows and a round-4 cut-off
is the loosest rank a programme ever admitted, so proportionally more programmes
land in **Safe**: at GM rank 76,983 the eligible split went 217/36/32
(Safe/Target/Reach) to 558/45/41. Re-tuning is a product decision that belongs
in its own change; the constants were deliberately left untouched so the data
swap stays attributable. Setting `round_strategy = 1` reproduces the
round-1-only view for comparison.
