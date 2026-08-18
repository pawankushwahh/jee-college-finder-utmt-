#!/usr/bin/env python3
"""Compile the six COMEDK UGET-2025 engineering PDFs into one tidy CSV.

Run from the repo root::

    python3 scripts/build_comedk_dataset.py                 # write the CSV
    python3 scripts/build_comedk_dataset.py --report-only   # parse + validate, write nothing

Requires ``pdfplumber`` (a build-time dependency only -- the app itself reads
the generated CSV and never touches a PDF).  Mirrors
``scripts/build_kcet_dataset.py`` in shape, conventions and output schema.

What the source documents actually are
--------------------------------------
The five cut-off documents are **not** row-per-cut-off tables.  Each is a wide
pivot grid printed from Excel:

  * rows are (College Code, College Name, **Seat Category**),
  * columns are one per course -- 68 of them,
  * a cell holds the closing rank, and a **blank cell means no seat was
    allotted** in that course/category that round.

68 course columns do not fit on a letter page, so each sheet is printed in
horizontal *blocks*: every block repeats the entire college list carrying the
next group of course columns.  Round 1 is 10 blocks x 16 pages = 160 pages.
This parser detects a block boundary where the college list restarts, which is
the only signal that holds across all five documents -- page counts per block
differ in every one of them (16 / 7 / 8 / 5 / 11).

The sixth document, the seat matrix, is a normal tall table: one row per
(college, course) with the seat split and the fee schedule.  It is published
*before* round 1, so it is the authoritative list of what exists.

Category coverage is deliberately uneven and must not be "repaired"
-------------------------------------------------------------------
COMEDK ran round 2 as a Kalyana-Karnataka-only mop-up and rounds 3-4 as
general-merit rounds::

    mock     GM + KKR        round 3  GM only
    round 1  GM + KKR        round 4  GM only
    round 2  KKR only

So a KKR cut-off for round 3 does not exist, and a GM cut-off for round 2 does
not exist.  Those are empty cells in the output, and they are *facts*, not
gaps to be interpolated.

Why geometry and not text
-------------------------
``pdftotext -layout`` is not safe on these documents, for the same reason it is
not safe on KEA's.  Concretely, on a first pass over these PDFs a text parser
gets all of the following wrong:

* **Course codes are 2, 3 or 4 letters.**  Alongside ``CS``/``CV`` there are
  ``AVE BDC BFD BID BLD CAD CBD CCA CCS CIT CSB CSD ECE ECV IAR IDA INT IST MAE
  ROB VLS``.  A ``[A-Z]{2}`` reading maps ``CAD-Computer...`` onto ``CA``, which
  is a different course sitting in an adjacent column.
* **Two codes are written with a space before the hyphen** (``IDA -Information
  Technology``, ``IAR - Virtual Reality``), so the code and the hyphen are
  separate words.
* **Near-duplicate codes sit in neighbouring columns**: ``RI``/``ROB``,
  ``VL``/``VLS``, ``CI``/``CIT``, ``CA``/``CAD``.  Snapping a value to the wrong
  column produces a perfectly plausible, silently wrong rank.
* **Rows wrap.**  89 seat-matrix rows put the college code on a different
  physical line from its numbers; line-oriented parsing drops them.
* **Row pitch is not constant** across documents: 18.6pt in round 1 but 9.6pt
  in the mock and 10.4pt in round 4.  A band tuned on round 1 merges adjacent
  rows in round 4.
* **One college is named "GM Institute of Technology"** (E051, Davangere), so
  scanning text for ``GM`` to locate the category column matches that college's
  *name* on every one of its rows.

So this parser works from word coordinates.  Column identity comes from the
course-code header words: their median x within a block forms the column grid,
and each value snaps to the nearest grid line.  Row identity comes from the
Seat Category cell, with a band of 45% of the measured row pitch either side,
so a wrapped name is gathered but a neighbouring row never is.

Output schema -- one row per (college, course, category)::

    exam_type,year,college_code,college_name,course_code,course_name,category,
    total_seats,category_seats,tuition_fee,other_fee,total_fee,
    closing_rank_mock,closing_rank_r1,closing_rank_r2,closing_rank_r3,closing_rank_r4

Rounds are widened; category is not -- the same reasoning as the KCET builder.
There are four rounds and the set is fixed for a year, so a column each makes
one programme's history readable at a glance.  ``category`` stays a row value:
COMEDK publishes exactly two codes (``GM``, ``KKR``) and they are disjoint
pools, so a category identifies its own pool and needs no ``seat_type`` column
of the kind KCET carries.

Two schema notes worth reading before consuming this file:

``closing_rank_mock`` is deliberately **not** named ``closing_rank_r0``.
    The mock round is a simulation published on 22.07.2025, before counselling
    opened; no seat was ever allotted from it.  The runtime loader discovers
    round columns with ``^closing_rank_r(\\d+)$``, so this name keeps the mock
    out of every round strategy while still carrying it in the dataset.  It is
    a demand signal, not an allotment.

Rows with no cut-off in any round are **kept**.
    1,003 of them: (college, course, category) combinations that had seats and
    never filled, across all five rounds.  They carry seats and fees with every
    rank column blank.  That is the vacancy signal, and it is only visible
    because the seat matrix is joined in here.  The runtime loader skips them
    for recommendation purposes -- a row with no cut-off has nothing to compare
    a rank against -- but they are in the file for anything that wants them.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import pdfplumber
except ImportError:  # pragma: no cover - dependency guidance
    sys.exit("pdfplumber is required: pip install pdfplumber")

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "raw_data" / "comedk"
# Written straight into the COMEDK package's data directory, same as the KCET
# builder: this file *is* what the engine reads at runtime, so a rebuild lands
# where it is used and the git diff is the review.
DEFAULT_OUT = REPO_ROOT / "app" / "disha" / "comedk" / "data" / "comedk_2025_all_rounds.csv"

YEAR = 2025
EXAM = "COMEDK"

# The two seat categories COMEDK publishes.  ``HKR`` is the seat matrix's
# spelling of ``KKR``: its column header says "HKR" (Hyderabad-Karnataka, the
# pre-2020 name) while its own footnote on the same page defines the code as
# "KKR: KALAYANA KARNATAKA REGION".  Same category, so the matrix header is
# normalised to KKR on read -- without this the seat join silently drops every
# KKR row.
CATEGORY_TOKENS = ("GM", "KKR", "HKR")
CANONICAL_CATEGORY = {"GM": "GM", "KKR": "KKR", "HKR": "KKR"}

# A course code is 2-4 capitals followed by a hyphen.  The hyphen is sometimes a
# separate word (``IDA -Information Technology``), so the trailing hyphen is
# optional here and the code is confirmed by its position instead.
COURSE_CODE = re.compile(r"^([A-Z]{2,4})\s*-")
BARE_CODE = re.compile(r"^([A-Z]{2,4})$")
COLLEGE_CODE = re.compile(r"^E\d{3}$")
RANK_VALUE = re.compile(r"^\d{2,6}$")

# Geometry, in PDF points.  Measured from the documents; see the module
# docstring for why none of these can be inferred from the text layer.
LINE_TOLERANCE = 2.0          # how finely words bucket into rendered lines
BAND_FRACTION = 0.45          # of the measured row pitch, either side of a row anchor
DATA_LEFT_EDGE = 415.0        # right of the Seat Category column on every cut-off page
HEADER_TOP, HEADER_BOTTOM = 100.0, 180.0   # the wrapped column-header block
SEAT_MATRIX_BAND = 11.0       # seat-matrix records are ~24pt apart
FOOTER_MARGIN = 22.0          # "Page N of M" band at the foot of every page

# Seat matrix column windows: Total Seats @551, GM @586, HKR @627, fees right of 640.
SM_TOTAL = (535.0, 568.0)
SM_GM = (570.0, 605.0)
SM_HKR = (610.0, 645.0)
SM_COURSE = (320.0, 560.0)
SM_NAME = (65.0, 320.0)
SM_FEE_LEFT = 640.0

# COMEDK's own printed grand-total row on the last page of the seat matrix.
# The build refuses to write a file that does not reconcile to it.
OFFICIAL_TOTAL_SEATS = 26_827
OFFICIAL_TOTAL_GM = 22_813
OFFICIAL_TOTAL_KKR = 4_014


@dataclass(frozen=True)
class Source:
    filename: str
    # None for the mock: it is carried in its own column, not as a round.
    round_no: Optional[int]
    column: str
    # Fragment that must appear in the document's own title line.  Round
    # identity is verified against the PDF rather than trusted from the
    # filename, same as the KCET builder.
    title_fragment: str
    # Categories this document is expected to publish.  Round 2 is a
    # Kalyana-Karnataka-only mop-up and rounds 3-4 are general-merit rounds;
    # asserting it here turns a silently truncated parse into a build failure.
    categories: Tuple[str, ...]


# Title fragments are matched against the **page's own text**, not the PDF
# metadata title, because the two disagree (the metadata still carries the
# source .xlsx filename). The fragment is the part that identifies the round,
# so a mislabelled filename cannot silently load as the wrong round.
SOURCES: Tuple[Source, ...] = (
    Source("comedk_mock.pdf", None, "closing_rank_mock",
           "Mock Round Allotment", ("GM", "KKR")),
    Source("comedk_round1.pdf", 1, "closing_rank_r1",
           "Round 1 Allotment", ("GM", "KKR")),
    Source("comedk_round2.pdf", 2, "closing_rank_r2",
           "Round 2 Allotment", ("KKR",)),
    Source("comedk_round3.pdf", 3, "closing_rank_r3",
           "Round 3 Allotment", ("GM",)),
    Source("comedk_round4_final.pdf", 4, "closing_rank_r4",
           "Round 4 Allotment", ("GM",)),
)

SEAT_MATRIX = "comedk_seat_matrix.pdf"
SEAT_MATRIX_TITLE = "Seat Availability"


@dataclass
class Stats:
    pages: int = 0
    blocks: int = 0
    colleges: int = 0
    cells: int = 0
    unmapped: int = 0
    ambiguous_blocks: List[str] = field(default_factory=list)
    collisions: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def page_words(page) -> List[dict]:
    """Words with an ``x`` centre and a ``y`` centre, the only two coordinates
    anything below cares about.

    The page footer is dropped here.  ``Page 8 of 70`` renders ``70`` at
    x=415 -- inside the data area -- so a footer that drifted up to within a
    row's band would be read as a closing rank in the leftmost course column.
    On these documents it sits ~29pt clear of the last data row, but that is
    luck rather than a guarantee, and the failure would be silent.
    """
    cutoff = float(page.height) - FOOTER_MARGIN
    out = []
    for w in page.extract_words(use_text_flow=False, keep_blank_chars=False):
        y = (w["top"] + w["bottom"]) / 2.0
        if y >= cutoff:
            continue
        out.append({
            "text": w["text"].strip(),
            "x": (w["x0"] + w["x1"]) / 2.0,
            "y": y,
        })
    return out


def cluster(values: Sequence[float], tolerance: float) -> List[float]:
    """Collapse near-identical coordinates into their means."""
    ordered = sorted(values)
    groups, current = [], [ordered[0]]
    for previous, value in zip(ordered, ordered[1:]):
        if value - previous > tolerance:
            groups.append(current)
            current = [value]
        else:
            current.append(value)
    groups.append(current)
    return [sum(g) / len(g) for g in groups]


def row_pitch(pages: List[List[dict]]) -> float:
    """Vertical distance between two consecutive data rows.

    Measured per document rather than assumed: it is 18.6pt in round 1 but
    9.6pt in the mock, and a band tuned on one merges rows in the other.
    """
    gaps: List[float] = []
    for words in pages[:6]:
        ys = sorted(w["y"] for w in words
                    if w["text"] in CATEGORY_TOKENS and w["y"] > HEADER_BOTTOM)
        gaps += [b - a for a, b in zip(ys, ys[1:]) if b - a > 1.0]
    if not gaps:
        raise ValueError("no category cells found -- is this a cut-off document?")
    return statistics.median(gaps)


def verify_title(page, fragment: str, filename: str) -> None:
    """Confirm the document is the one the source table claims it is."""
    text = (page.extract_text() or "")[:400]
    if fragment.lower() not in text.lower():
        sys.exit(
            f"{filename}: title check failed -- expected {fragment!r} in the "
            f"first page's text. Refusing to guess which round this is."
        )


# ---------------------------------------------------------------------------
# Cut-off documents
# ---------------------------------------------------------------------------
def block_boundaries(pages: List[List[dict]]) -> List[List[int]]:
    """Split pages into horizontal blocks.

    Each block repeats the whole college list with the next group of course
    columns, so a block starts wherever the first college code on a page is
    lower than the first college code on the page before.  This is the only
    boundary signal that holds across all five documents: pages-per-block is 16,
    7, 8, 5 and 11 respectively, and the column-header text is too mangled by
    wrapping to fingerprint reliably.
    """
    firsts: List[Optional[str]] = []
    for words in pages:
        codes = sorted(w["text"] for w in words
                       if COLLEGE_CODE.match(w["text"]) and w["y"] > HEADER_BOTTOM)
        firsts.append(codes[0] if codes else None)

    starts = [0] + [
        i for i in range(1, len(pages))
        if firsts[i] and firsts[i - 1] and firsts[i] < firsts[i - 1]
    ]
    return [list(range(s, e)) for s, e in zip(starts, starts[1:] + [len(pages)])]


def column_grid(pages: List[List[dict]], block: List[int]) -> List[Tuple[float, str]]:
    """The block's course columns as (x centre, course code), left to right.

    Built from the header words: a course header is centred over its column, so
    the median x of a code word across the block's pages is that column's
    centre.  Codes whose hyphen was split into a separate word (``IDA -``) are
    picked up by matching a bare 2-4 capital word that is immediately followed
    by a word starting with a hyphen.
    """
    positions: Dict[str, List[float]] = defaultdict(list)
    for index in block:
        header = [w for w in pages[index]
                  if HEADER_TOP < w["y"] < HEADER_BOTTOM and w["x"] > DATA_LEFT_EDGE]
        header.sort(key=lambda w: (w["y"], w["x"]))
        for position, word in enumerate(header):
            match = COURSE_CODE.match(word["text"])
            if match:
                code = match.group(1)
            else:
                bare = BARE_CODE.match(word["text"])
                following = header[position + 1] if position + 1 < len(header) else None
                if bare and following and following["text"].startswith("-"):
                    code = bare.group(1)
                else:
                    continue
            if code in CATEGORY_TOKENS:
                continue
            positions[code].append(word["x"])

    grid = sorted((statistics.median(xs), code) for code, xs in positions.items())
    return grid


def parse_cutoff_pdf(path: Path, source: Source, stats: Stats) -> Dict[Tuple[str, str, str], float]:
    """Return ``{(college_code, course_code, category): closing_rank}``."""
    with pdfplumber.open(path) as pdf:
        verify_title(pdf.pages[0], source.title_fragment, source.filename)
        pages = [page_words(p) for p in pdf.pages]

    stats.pages = len(pages)
    pitch = row_pitch(pages)
    band = pitch * BAND_FRACTION
    blocks = block_boundaries(pages)
    stats.blocks = len(blocks)

    values: Dict[Tuple[str, str, str], float] = {}
    colleges: set = set()

    for block in blocks:
        grid = column_grid(pages, block)
        if not grid:
            continue

        # A gap of roughly two column pitches means a column's header code was
        # not recognised, so values in it would snap to a neighbour. Report it
        # rather than writing a silently misattributed rank.
        centres = [x for x, _ in grid]
        if len(centres) > 2:
            pitches = [b - a for a, b in zip(centres, centres[1:])]
            typical = statistics.median(pitches)
            if any(p > typical * 1.6 for p in pitches):
                stats.ambiguous_blocks.append(
                    f"p{block[0] + 1}: {[c for _, c in grid]}"
                )

        for index in block:
            words = pages[index]
            for anchor in words:
                if anchor["text"] not in CATEGORY_TOKENS or anchor["y"] <= HEADER_BOTTOM:
                    continue
                category = CANONICAL_CATEGORY[anchor["text"]]
                row = [w for w in words if abs(w["y"] - anchor["y"]) <= band]
                college = next(
                    (w["text"] for w in row if COLLEGE_CODE.match(w["text"])), None
                )
                if not college:
                    continue
                colleges.add(college)
                for word in row:
                    if word["x"] <= DATA_LEFT_EDGE or not RANK_VALUE.match(word["text"]):
                        continue
                    _, code = min(grid, key=lambda g: abs(g[0] - word["x"]))
                    key = (college, code, category)
                    rank = float(word["text"])
                    # Two different ranks landing on one key means two course
                    # columns snapped to the same grid line -- i.e. a column
                    # header was not recognised and its values were attributed
                    # to a neighbour. That is the failure mode this parser
                    # exists to avoid, so it is fatal rather than last-wins.
                    if key in values and values[key] != rank:
                        stats.collisions.append(
                            f"{college}/{code}/{category}: {values[key]:g} vs {rank:g}"
                        )
                    values[key] = rank

    stats.colleges = len(colleges)
    stats.cells = len(values)

    if stats.collisions:
        sys.exit(
            f"{source.filename}: {len(stats.collisions)} column collision(s) -- "
            f"two course columns resolved to the same code, so at least one "
            f"rank would be attributed to the wrong course. First few: "
            + "; ".join(stats.collisions[:5])
        )

    found = {category for _, _, category in values}
    expected = set(source.categories)
    if found != expected:
        sys.exit(
            f"{source.filename}: expected categories {sorted(expected)} but "
            f"parsed {sorted(found)}. Refusing to write a partial round."
        )
    return values


def parse_college_names(path: Path) -> Dict[str, str]:
    """``{college_code: college_name}`` taken from a cut-off document.

    Names come from here rather than the seat matrix because the cut-off sheets
    render a college name on a single line in most blocks, while the seat matrix
    wraps long ones across two lines inside the same cell.
    """
    names: Dict[str, str] = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page_words(page)
            pitch_words = [w for w in words
                           if w["text"] in CATEGORY_TOKENS and w["y"] > HEADER_BOTTOM]
            for anchor in pitch_words:
                row = [w for w in words if abs(w["y"] - anchor["y"]) <= 6.0]
                college = next(
                    (w["text"] for w in row if COLLEGE_CODE.match(w["text"])), None
                )
                if not college or college in names:
                    continue
                name = " ".join(
                    w["text"] for w in sorted(row, key=lambda w: (w["y"], w["x"]))
                    if 65.0 < w["x"] < anchor["x"] - 20.0
                    and not COLLEGE_CODE.match(w["text"])
                )
                if name:
                    names[college] = " ".join(name.split())
    return names


# ---------------------------------------------------------------------------
# Seat matrix
# ---------------------------------------------------------------------------
def parse_seat_matrix(path: Path) -> Tuple[Dict[Tuple[str, str], dict], Dict[str, str]]:
    """Return ``{(college, course): {...seats, fees}}`` and ``{course: name}``.

    Anchored on the Total Seats cell rather than on a text line, because 89 of
    the 1,067 rows wrap their course name and put the college code on a
    different physical line from its numbers.
    """
    seats: Dict[Tuple[str, str], dict] = {}
    course_names: Dict[str, str] = {}

    with pdfplumber.open(path) as pdf:
        verify_title(pdf.pages[0], SEAT_MATRIX_TITLE, SEAT_MATRIX)
        for page in pdf.pages:
            words = page_words(page)
            anchors = [w for w in words
                       if SM_TOTAL[0] <= w["x"] <= SM_TOTAL[1]
                       and re.fullmatch(r"\d{1,4}", w["text"])
                       and w["y"] > 85.0]
            for anchor in anchors:
                row = sorted(
                    (w for w in words if abs(w["y"] - anchor["y"]) <= SEAT_MATRIX_BAND),
                    key=lambda w: (w["y"], w["x"]),
                )
                college = next(
                    (w["text"] for w in row if COLLEGE_CODE.match(w["text"])), None
                )
                course = None
                course_at = None
                for position, word in enumerate(sorted(row, key=lambda w: w["x"])):
                    if not (SM_COURSE[0] < word["x"] < SM_COURSE[1]):
                        continue
                    match = COURSE_CODE.match(word["text"])
                    if match:
                        course, course_at = match.group(1), word["x"]
                        break
                    bare = BARE_CODE.match(word["text"])
                    if bare:
                        course, course_at = bare.group(1), word["x"]
                        break
                if not college or not course:
                    continue

                gm = kkr = None
                fees: List[Tuple[float, int]] = []
                for word in row:
                    if re.fullmatch(r"\d{1,4}", word["text"]):
                        if SM_GM[0] <= word["x"] <= SM_GM[1]:
                            gm = int(word["text"])
                        elif SM_HKR[0] <= word["x"] <= SM_HKR[1]:
                            kkr = int(word["text"])
                    elif "," in word["text"] and word["x"] > SM_FEE_LEFT:
                        digits = word["text"].replace(",", "")
                        if digits.isdigit():
                            fees.append((word["x"], int(digits)))
                fees.sort()
                amounts = [amount for _, amount in fees]

                seats[(college, course)] = {
                    "total_seats": int(anchor["text"]),
                    "GM": gm or 0,
                    "KKR": kkr or 0,
                    "tuition_fee": amounts[0] if len(amounts) > 0 else "",
                    "other_fee": amounts[1] if len(amounts) > 1 else "",
                    "total_fee": amounts[2] if len(amounts) > 2 else "",
                }

                if course not in course_names:
                    name = " ".join(
                        w["text"] for w in row
                        if w["x"] >= (course_at or 0) - 1 and w["x"] < SM_TOTAL[0]
                    )
                    name = re.sub(r"^[A-Z]{2,4}\s*-\s*", "", " ".join(name.split()))
                    if name:
                        course_names[course] = name

                if college in course_names:  # pragma: no cover - defensive
                    pass
    return seats, course_names


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
FIELDNAMES = [
    "exam_type", "year",
    "college_code", "college_name",
    "course_code", "course_name",
    "category",
    "total_seats", "category_seats",
    "tuition_fee", "other_fee", "total_fee",
]


def assemble(
    per_source: Dict[str, Dict[Tuple[str, str, str], float]],
    seats: Dict[Tuple[str, str], dict],
    college_names: Dict[str, str],
    course_names: Dict[str, str],
) -> Tuple[List[dict], List[str]]:
    """One row per (college, course, category), rounds widened into columns.

    The row set is the **union** of the seat matrix and every cut-off document:
    a combination with seats but no cut-off anywhere is a vacancy and is kept
    with empty rank columns; a cut-off with no matching seat row is kept too,
    with empty seat columns, rather than silently dropped.
    """
    rank_columns = [source.column for source in SOURCES]

    keys: set = set()
    for (college, course), row in seats.items():
        for category in ("GM", "KKR"):
            if row[category]:
                keys.add((college, course, category))
    for values in per_source.values():
        keys.update(values)

    rows: List[dict] = []
    for college, course, category in sorted(keys):
        seat_row = seats.get((college, course))
        record = {
            "exam_type": EXAM,
            "year": YEAR,
            "college_code": college,
            "college_name": college_names.get(college, ""),
            "course_code": course,
            "course_name": course_names.get(course, ""),
            "category": category,
            "total_seats": seat_row["total_seats"] if seat_row else "",
            "category_seats": seat_row[category] if seat_row else "",
            "tuition_fee": seat_row["tuition_fee"] if seat_row else "",
            "other_fee": seat_row["other_fee"] if seat_row else "",
            "total_fee": seat_row["total_fee"] if seat_row else "",
        }
        for source in SOURCES:
            value = per_source[source.column].get((college, course, category))
            record[source.column] = "" if value is None else f"{value:g}"
        rows.append(record)

    return rows, FIELDNAMES + rank_columns


def validate(rows: List[dict], seats: Dict[Tuple[str, str], dict]) -> List[str]:
    """Structural checks plus a reconciliation against COMEDK's own totals."""
    problems: List[str] = []
    rank_columns = [source.column for source in SOURCES]

    for row in rows:
        if not COLLEGE_CODE.match(row["college_code"]):
            problems.append(f"malformed college code: {row['college_code']}")
        if not re.fullmatch(r"[A-Z]{2,4}", row["course_code"]):
            problems.append(f"malformed course code: {row['course_code']}")
        if row["category"] not in ("GM", "KKR"):
            problems.append(f"unexpected category: {row['category']}")
        if not row["college_name"]:
            problems.append(f"missing college name: {row['college_code']}")
        for column in rank_columns:
            raw = row[column]
            if raw == "":
                continue
            try:
                rank = float(raw)
            except ValueError:
                problems.append(f"non-numeric rank {raw!r} in {column}")
                continue
            if rank <= 0:
                problems.append(f"non-positive rank {raw!r} in {column}")

    # Round 2 is KKR-only and rounds 3-4 are GM-only.  If either ever carries
    # the other category, the block/column mapping has drifted.
    for column, allowed in (("closing_rank_r2", "KKR"),
                            ("closing_rank_r3", "GM"),
                            ("closing_rank_r4", "GM")):
        wrong = [r for r in rows if r[column] != "" and r["category"] != allowed]
        if wrong:
            problems.append(
                f"{column} has {len(wrong)} rows in the wrong category "
                f"(expected {allowed} only)"
            )

    # Reconcile against the grand-total row COMEDK prints on the seat matrix's
    # last page.  This is the check that catches a dropped or double-counted
    # course row, which nothing structural above would notice.
    total = sum(v["total_seats"] for v in seats.values())
    gm = sum(v["GM"] for v in seats.values())
    kkr = sum(v["KKR"] for v in seats.values())
    if (total, gm, kkr) != (OFFICIAL_TOTAL_SEATS, OFFICIAL_TOTAL_GM, OFFICIAL_TOTAL_KKR):
        problems.append(
            f"seat matrix does not reconcile with the document's printed TOTAL: "
            f"parsed {total}/{gm}/{kkr}, expected "
            f"{OFFICIAL_TOTAL_SEATS}/{OFFICIAL_TOTAL_GM}/{OFFICIAL_TOTAL_KKR}"
        )
    mismatched = [k for k, v in seats.items() if v["total_seats"] != v["GM"] + v["KKR"]]
    if mismatched:
        problems.append(
            f"{len(mismatched)} seat-matrix rows where Total != GM + KKR, "
            f"e.g. {mismatched[:3]}"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the COMEDK all-rounds CSV.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report-only", action="store_true",
                        help="parse and validate but write no file")
    args = parser.parse_args()

    for source in SOURCES:
        if not (RAW_DIR / source.filename).exists():
            sys.exit(f"missing source PDF: {RAW_DIR / source.filename}")
    if not (RAW_DIR / SEAT_MATRIX).exists():
        sys.exit(f"missing source PDF: {RAW_DIR / SEAT_MATRIX}")

    print("Seat matrix")
    seats, course_names = parse_seat_matrix(RAW_DIR / SEAT_MATRIX)
    total = sum(v["total_seats"] for v in seats.values())
    print(f"  {SEAT_MATRIX:28} rows={len(seats):5d} "
          f"colleges={len({c for c, _ in seats}):3d} "
          f"courses={len({b for _, b in seats}):3d} seats={total}")

    print("\nCut-off documents")
    per_source: Dict[str, Dict[Tuple[str, str, str], float]] = {}
    for source in SOURCES:
        stats = Stats()
        per_source[source.column] = parse_cutoff_pdf(
            RAW_DIR / source.filename, source, stats
        )
        label = "mock" if source.round_no is None else f"r{source.round_no}"
        print(f"  {source.filename:28} {label:5} pages={stats.pages:4d} "
              f"blocks={stats.blocks:3d} colleges={stats.colleges:3d} "
              f"cut-offs={stats.cells:5d} "
              f"categories={','.join(source.categories)}")
        for note in stats.ambiguous_blocks:
            print(f"      uneven column grid -- {note}")

    college_names = parse_college_names(RAW_DIR / "comedk_round1.pdf")
    print(f"\nCollege names resolved: {len(college_names)}")

    rows, fieldnames = assemble(per_source, seats, college_names, course_names)

    rank_columns = [s.column for s in SOURCES]
    with_cutoff = [r for r in rows if any(r[c] for c in rank_columns)]
    vacant = len(rows) - len(with_cutoff)
    print(f"Rows assembled: {len(rows)} "
          f"({len(with_cutoff)} with a cut-off, {vacant} vacant in every round)")

    problems = validate(rows, seats)
    if problems:
        print(f"\nVALIDATION FAILED -- {len(problems)} problem(s):")
        for problem in problems[:20]:
            print(f"  - {problem}")
        return 1
    print("Validation passed (including reconciliation to the printed seat total).")

    if args.report_only:
        print("\n--report-only: nothing written.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {args.out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
