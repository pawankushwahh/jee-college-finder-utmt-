# COMEDK (UGET) 2025 — raw source status

**Engineering only.** Mock round, all four counselling rounds, and the
pre-counselling seat matrix. Nothing missing.

> **Compiled output:** `app/disha/comedk/data/comedk_2025_all_rounds.csv`
> (2,131 rows) is built from the six PDFs below by
> `scripts/build_comedk_dataset.py`, and **is the file the COMEDK engine
> reads**. **[docs/DATA_PIPELINE.md §7](../../docs/DATA_PIPELINE.md#7-comedk--building-the-csv)
> is the runbook** — what each document is, how to rebuild, and how a rebuild is
> verified. This file only records what was downloaded.

## Files

| File | Document | Notified | Pages | Categories |
|---|---|---|---|---|
| `comedk_seat_matrix.pdf` | Final Engineering Seat Availability and Fee, before round 1 | 18.07.2025 | 52 | GM + HKR |
| `comedk_mock.pdf` | Mock Round Allotment cut-off ranks | 22.07.2025 | 77 | GM + KKR |
| `comedk_round1.pdf` | Cut-off ranks after Round 1 Allotment | 28.07.2025 | 160 | GM + KKR |
| `comedk_round2.pdf` | Cut-off ranks after Round 2 Allotment | 12.08.2025 | 70 | **KKR only** |
| `comedk_round3.pdf` | Cut-off ranks after Round 3 Allotment | 22.08.2025 | 80 | **GM only** |
| `comedk_round4_final.pdf` | Cut-off ranks after Round 4 Allotment (final) | 05.09.2025 | 50 | **GM only** |

## Things that will trip you up

**The rounds are not category-symmetric.** COMEDK ran round 2 as a
Kalyana-Karnataka-only mop-up and rounds 3–4 as general-merit rounds. A KKR
cut-off for round 3 does not exist, and a GM cut-off for round 2 does not
exist. The builder asserts each document's category set, so a document that
does not match its expected categories fails the build rather than loading
half-empty.

**The cut-off PDFs are wide pivot grids, not tables.** Rows are (college,
category); columns are the 68 courses; a blank cell means no seat was allotted.
Each sheet prints in horizontal blocks that repeat the whole college list with
the next group of columns — round 1 is 10 blocks × 16 pages.

**`HKR` and `KKR` are the same category.** The seat matrix's column header says
`HKR` (Hyderabad-Karnataka, the pre-2020 name) while its own footnote on the
same page defines the code as "KKR: KALAYANA KARNATAKA REGION". The builder
normalises to `KKR`; joining on the raw string drops every KKR row.

**The mock round is a simulation.** Published before counselling opened; no seat
was ever allotted from it. It is kept in the CSV as `closing_rank_mock` —
deliberately not `closing_rank_r0`, so it can never be selected as "the"
cut-off by a round strategy.

**Two footnotes on the seat matrix carry real constraints**, neither of which
any engine reads yet:

- E055, GSSS Institute of Engineering & Technology for Women, is women-only.
  COMEDK warns that a male candidate selecting it has the seat cancelled later.
- Colleges may collect a further ₹10,000–₹20,000 per year for special skill
  labs, plus university fees, on top of the `total_fee` column.

## Verification anchor

The seat matrix prints its own grand total on page 52:

```
TOTAL    26,827    22,813    4,014
```

The build reconciles to it exactly (1,067 course rows; `Total = GM + KKR` on
every one) and refuses to write if it does not. This is the check that catches a
dropped or double-counted row.

Note that **26,827 does not match the "19,531 seats" figure** in some 2025
COMEDK reporting. 26,827 is what this document totals; the discrepancy is
unresolved and worth chasing before either number is shown to a user.
