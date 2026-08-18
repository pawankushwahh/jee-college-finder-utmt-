#!/usr/bin/env python3
"""Compile the six KEA UGCET-2025 engineering cut-off PDFs into one tidy CSV.

Run from the repo root::

    python3 scripts/build_kcet_dataset.py                    # write the CSV
    python3 scripts/build_kcet_dataset.py --report-only      # parse + validate, write nothing

Requires ``pdfplumber`` (a build-time dependency only -- the app itself reads
the generated CSV and never touches a PDF).

Why geometry and not text
-------------------------
``pdftotext -layout`` is not safe on these documents.  KEA renders a cut-off
wider than its column by pushing the overflow onto the *next* text line, so
``254427.5`` comes out as ``254427.`` on the data line and a bare ``5`` on the
line below -- which a line-oriented parser reads as ``254427``, or worse, glues
onto the next course name.  The same happens to wrapped course names, which is
how the previous extraction produced ``ARTIFICIAL`` and
``INTELLIGENCE AND DATA SCIENCE CIVIL`` as separate "courses".

So this parser works from word coordinates instead:

* Column identity comes from the ``Course Name | 1G | 1K | ...`` header row --
  every value is horizontally centred on its category header, so each value is
  assigned to the nearest header centre.  This also handles the category set
  changing between rounds (rounds 1 has 24 categories; rounds 2 and 3 add
  ``GMP``, ``NRI``, ``OPN`` and ``OTH`` for 28).
* A row's course name is whatever sits left of the first category column.
* A line carrying no values is a continuation of the name above it.
* A bare digit-run landing in a column whose current value ends in ``.`` is a
  wrapped decimal and gets appended to that value.

Output schema -- one row per programme, one column per round::

    exam_type,year,seat_type,college_code,college_name,course_name,category,
    closing_rank_r1,closing_rank_r2,closing_rank_r3

Parsing produces one record per (programme, round); ``pivot_rounds`` reshapes
those into the wide form just before writing, deriving the round columns from
the rounds actually parsed. A blank round cell means the programme allotted no
seat that round -- ``--`` in the PDF -- so KEA published no cut-off for it.
That is information, not missing data.

Rounds are widened; category is not. There are three rounds and the set is
fixed for a year, so a column each makes one programme's history readable at a
glance. The category set, by contrast, *changes* between rounds (24 codes in
round 1, 28 in rounds 2-3), so category columns would need a per-round map and
would be mostly empty -- category stays a row value.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import pdfplumber
except ImportError:  # pragma: no cover - dependency guidance
    sys.exit("pdfplumber is required: pip install pdfplumber")

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "raw_data" / "kcet"
# Written straight into the KCET package's data directory: this file *is* what
# the engine reads at runtime, so a rebuild lands where it is used and the git
# diff is the review. Nothing is written until every document passes its header
# check and the output passes validation.
DEFAULT_OUT = REPO_ROOT / "app" / "disha" / "kcet" / "data" / "kcet_2025_all_rounds.csv"

YEAR = 2025
EXAM = "KCET"

# Vertical distance between two rendered text lines, in points.  Used only to
# decide how finely to bucket words into lines.
LINE_TOLERANCE = 2.0

# A value must sit within this many points of a header centre to be trusted.
COLUMN_TOLERANCE = 14.0

# Courses that are not engineering.  KEA's *engineering* documents nonetheless
# carry a handful of architecture / design / planning programmes: the round-1
# final strips them, but rounds 2 and 3 put them back, so filtering here is what
# keeps the college set comparable across rounds.  Every drop is reported.
NON_ENGINEERING = re.compile(
    r"^(B\.?\s*PLAN|BACHELOR OF (ARCHITECTURE|DESIGN)|PLANNING|DESIGN)\b",
    re.IGNORECASE,
)

HEADER_NOISE = (
    "KARNATAKA EXAMINATIONS AUTHORITY",
    "Non-Interactive Admission System",
    "UGCET-2025",
    "Seat Type:",
    "Generated on:",
)


@dataclass(frozen=True)
class Source:
    filename: str
    round_no: int
    seat_type: str
    # Fragment that must appear in the document's own title line.  Round identity
    # is verified against the PDF rather than trusted from the filename.
    title_fragment: str
    seat_fragment: str
    expected_colleges: int


SOURCES: Tuple[Source, ...] = (
    Source("kcet_round1_rok.pdf", 1, "ROK",
           "UGCET-2025 ALLOTMENT CUT-OFF RANKS", "Rest Of karnataka", 224),
    Source("kcet_round1_hk.pdf", 1, "HK",
           "UGCET-2025 ALLOTMENT CUT-OFF RANKS", "371(j) Kalyana karnataka", 224),
    Source("kcet_round2_rok.pdf", 2, "ROK",
           "UGCET-2025 SESSION-2 ALLOTMENT CUT-OFF RANKS", "Rest Of karnataka", 228),
    Source("kcet_round2_hk.pdf", 2, "HK",
           "UGCET-2025 SESSION-2 ALLOTMENT CUT-OFF RANKS", "371(j) Kalyana karnataka", 228),
    Source("kcet_round3_rok.pdf", 3, "ROK",
           "UGCET-2025 THIRD ROUND CUT-OFF RANKS", "Rest Of karnataka", 229),
    Source("kcet_round3_hk.pdf", 3, "HK",
           "UGCET-2025 THIRD ROUND CUT-OFF RANKS", "371(j) Kalyana karnataka", 229),
)


@dataclass
class Stats:
    rows: int = 0
    colleges: int = 0
    fractional: int = 0
    decimal_repairs: int = 0
    name_joins: int = 0
    dropped_non_engineering: int = 0
    dropped_courses: Counter = field(default_factory=Counter)
    duplicates: int = 0
    off_grid: int = 0
    college_name_wraps: int = 0
    name_repairs: int = 0
    name_variants: int = 0
    bracket_repairs: int = 0


def group_into_lines(words: Sequence[dict]) -> List[List[dict]]:
    """Bucket words into rendered text lines, ordered top-to-bottom."""
    buckets: Dict[float, List[dict]] = defaultdict(list)
    for word in words:
        buckets[round(word["top"] / LINE_TOLERANCE)].append(word)
    return [
        sorted(buckets[key], key=lambda w: w["x0"])
        for key in sorted(buckets)
    ]


def line_text(line: Sequence[dict]) -> str:
    return " ".join(w["text"] for w in line)


def is_header_row(line: Sequence[dict]) -> bool:
    text = line_text(line)
    return text.startswith("Course Name") and len(line) > 5


def parse_columns(line: Sequence[dict]) -> Tuple[List[str], List[float], float]:
    """From a header row, return (labels, centres, name/value boundary x)."""
    categories = [w for w in line if w["text"] not in ("Course", "Name")]
    labels = [w["text"] for w in categories]
    centres = [(w["x0"] + w["x1"]) / 2 for w in categories]
    pitch = (centres[1] - centres[0]) if len(centres) > 1 else 26.0
    boundary = centres[0] - pitch / 2
    return labels, centres, boundary


def nearest_column(centre: float, centres: Sequence[float]) -> Tuple[int, float]:
    best = min(range(len(centres)), key=lambda i: abs(centres[i] - centre))
    return best, abs(centres[best] - centre)


class Row:
    """A course row under construction."""

    __slots__ = ("name_parts", "values")

    def __init__(self, name_parts: List[str], values: Dict[int, str]):
        self.name_parts = name_parts
        self.values = values

    @property
    def course(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.name_parts)).strip()


def parse_pdf(path: Path, source: Source, stats: Stats) -> List[dict]:
    records: List[dict] = []
    colleges: set = set()

    college_code: Optional[str] = None
    college_name: str = ""
    labels: List[str] = []
    centres: List[float] = []
    boundary: float = 75.0
    awaiting_header = False
    pending: Optional[Row] = None

    def flush() -> None:
        nonlocal pending
        if pending is None:
            return
        course = pending.course
        if course and college_code:
            if NON_ENGINEERING.match(course):
                stats.dropped_non_engineering += len(pending.values)
                stats.dropped_courses[f"{college_code} {course}"] += 1
            else:
                for idx, raw in sorted(pending.values.items()):
                    value = raw.rstrip(".")
                    if not value:
                        continue
                    records.append(
                        {
                            "exam_type": EXAM,
                            "year": YEAR,
                            "round": source.round_no,
                            "seat_type": source.seat_type,
                            "college_code": college_code,
                            "college_name": college_name,
                            "course_name": course,
                            "category": labels[idx],
                            "closing_rank": value,
                        }
                    )
                    if "." in value:
                        stats.fractional += 1
        pending = None

    with pdfplumber.open(path) as pdf:
        first_page_text = pdf.pages[0].extract_text() or ""
        if source.title_fragment not in first_page_text:
            raise SystemExit(
                f"{path.name}: title check failed -- expected "
                f"{source.title_fragment!r} in the document header"
            )
        if source.seat_fragment not in first_page_text:
            raise SystemExit(
                f"{path.name}: seat-type check failed -- expected "
                f"{source.seat_fragment!r} in the document header"
            )

        for page in pdf.pages:
            for line in group_into_lines(page.extract_words()):
                text = line_text(line)

                if text.startswith("College:"):
                    flush()
                    college_code = line[1]["text"] if len(line) > 1 else None
                    # Some documents render the code as "(E001)Name" instead of
                    # "E001 Name"; normalise both to a bare code.
                    match = re.match(r"\(?([A-Z]\d{3})\)?(.*)", college_code or "")
                    if match:
                        college_code = match.group(1)
                        trailing = match.group(2).strip()
                    else:
                        trailing = ""
                    rest = " ".join(w["text"] for w in line[2:])
                    college_name = re.sub(r"\s+", " ", f"{trailing} {rest}").strip()
                    if college_code:
                        colleges.add(college_code)
                    awaiting_header = True
                    continue

                if is_header_row(line):
                    flush()
                    labels, centres, boundary = parse_columns(line)
                    awaiting_header = False
                    continue

                if any(noise in text for noise in HEADER_NOISE):
                    continue
                if not college_code or not labels:
                    continue

                name_words = [w for w in line if w["x1"] <= boundary]
                value_words = [w for w in line if w["x0"] > boundary]

                if awaiting_header:
                    # Between "College:" and the header row, a value-less line is
                    # the tail of a wrapped college name -- never a course.
                    if name_words and not value_words:
                        college_name = re.sub(
                            r"\s+", " ",
                            f"{college_name} {' '.join(w['text'] for w in name_words)}",
                        ).strip()
                        stats.college_name_wraps += 1
                    continue

                if not value_words:
                    if name_words and pending is not None:
                        pending.name_parts.append(
                            " ".join(w["text"] for w in name_words)
                        )
                        stats.name_joins += 1
                    continue

                # Decide: is this a fresh data row, or the overflow tail of the
                # row above?
                #
                # KEA renders *every* cell of a data row, writing "--" where
                # there is no cut-off, so a real row carries one value word per
                # category column.  An overflow tail carries one or two bare
                # digit-runs and nothing else.  That count is the reliable
                # discriminator.
                #
                # Do not test for a trailing "." on the value being continued:
                # ranks can carry three decimals, so "15223.875" is split as
                # "15223.87" + "5" and the truncated half ends in a digit.
                # Testing the dot silently turned those tails into phantom
                # courses whose only cut-off was the stray digit.
                def is_overflow() -> bool:
                    if pending is None or not value_words:
                        return False
                    if len(value_words) >= len(centres) - 1:
                        return False
                    for word in value_words:
                        if not word["text"].isdigit():
                            return False
                        idx, _ = nearest_column(
                            (word["x0"] + word["x1"]) / 2, centres
                        )
                        # An overflow can only ever continue a cell that already
                        # holds part of a number.
                        if not pending.values.get(idx, ""):
                            return False
                    return True

                if is_overflow():
                    assert pending is not None
                    for word in value_words:
                        idx, _ = nearest_column(
                            (word["x0"] + word["x1"]) / 2, centres
                        )
                        pending.values[idx] += word["text"]
                        stats.decimal_repairs += 1
                    if name_words:
                        pending.name_parts.append(
                            " ".join(w["text"] for w in name_words)
                        )
                        stats.name_joins += 1
                    continue

                flush()
                values: Dict[int, str] = {}
                for word in value_words:
                    token = word["text"]
                    if token == "--":
                        continue
                    idx, distance = nearest_column(
                        (word["x0"] + word["x1"]) / 2, centres
                    )
                    if distance > COLUMN_TOLERANCE:
                        stats.off_grid += 1
                        continue
                    values[idx] = token
                pending = Row([" ".join(w["text"] for w in name_words)], values)

        flush()

    stats.colleges = len(colleges)
    if len(colleges) != source.expected_colleges:
        print(
            f"  ! college count {len(colleges)} != expected "
            f"{source.expected_colleges} for {path.name}",
            file=sys.stderr,
        )
    return records


def canonicalise_courses(records: List[dict], stats: Stats) -> None:
    """Repair course names that the PDF wrapped mid-word.

    The name column is narrow, so KEA splits a long word across two lines with
    no hyphen: ``COMPUTER SCIENCE AND ENGG(INTERNE`` + ``T OF THINGS)``.
    Rejoining with a space yields ``INTERNE T OF THINGS``.  The column is
    narrower in rounds 2 and 3 (28 categories, not 24), so the *same* course
    splits at a different character in different rounds and ends up as two
    distinct names in the compiled table.

    Geometry cannot fix this -- a wrap at a space and a wrap mid-word look
    identical -- but arithmetic can: a mid-word split always adds one token.
    So among all names that agree once whitespace is removed, the variant with
    the fewest tokens is the unsplit one.
    """
    # Step 1: the one split the despaced-key fold below cannot repair -- a
    # course whose name is wrapped the *same* way in every round, so no unsplit
    # variant exists to fold onto.  These all break in the same place: an
    # opening bracket fills the column and exactly one letter follows it, giving
    # "ENGINEERING(D ATA SCIENCE)".  Matching only a lone letter directly after
    # "(" keeps this off legitimate names like "(AI &ML)" and "(Dev Ops)".
    #
    # Not cosmetic: "(D ATA SCIENCE)" does not contain the token "DATA", so
    # classify_kcet_branch tags it 'cse' and misses 'ai_ds'.
    for row in records:
        repaired = re.sub(r"\(([A-Za-z]) (?=[A-Za-z])", r"(\1", row["course_name"])
        if repaired != row["course_name"]:
            row["course_name"] = repaired
            stats.bracket_repairs += 1

    # Step 2: fold variants that differ only in where a word was split.
    variants: Dict[str, Counter] = defaultdict(Counter)
    for row in records:
        key = re.sub(r"\s+", "", row["course_name"]).upper()
        variants[key][row["course_name"]] += 1

    canonical: Dict[str, str] = {}
    for key, seen in variants.items():
        if len(seen) == 1:
            continue
        # Fewest tokens wins; ties broken by whichever occurs more often.
        best = min(seen, key=lambda name: (len(name.split()), -seen[name]))
        for name in seen:
            if name != best:
                canonical[name] = best

    if not canonical:
        return
    for row in records:
        replacement = canonical.get(row["course_name"])
        if replacement:
            row["course_name"] = replacement
            stats.name_repairs += 1
    stats.name_variants = len(canonical)


def dedupe(records: List[dict], stats: Stats) -> List[dict]:
    seen: set = set()
    out: List[dict] = []
    for row in records:
        key = (
            row["round"], row["seat_type"], row["college_code"],
            row["course_name"], row["category"],
        )
        if key in seen:
            stats.duplicates += 1
            continue
        seen.add(key)
        out.append(row)
    return out


def round_column(round_no: int) -> str:
    return f"closing_rank_r{round_no}"


def pivot_rounds(records: List[dict]) -> Tuple[List[dict], List[int]]:
    """Reshape one-row-per-(programme, round) into one row per programme, with
    a column per round.

    Rounds are a safe axis to widen on: there are three of them, the set is
    fixed for a given year, and a blank cell carries real meaning — the
    programme allotted no seat that round, so KEA published no cut-off for it.

    This is *not* the same as widening on category, which the long format
    deliberately avoids: the category set changes between rounds (24 in round 1,
    28 in rounds 2-3), so category columns would need a per-round map and would
    be mostly empty. Category stays a row value.
    """
    rounds = sorted({int(r["round"]) for r in records})
    wide: Dict[tuple, dict] = {}
    for row in records:
        key = (
            row["seat_type"], row["college_code"],
            row["course_name"], row["category"],
        )
        entry = wide.get(key)
        if entry is None:
            entry = wide[key] = {
                "exam_type": row["exam_type"],
                "year": row["year"],
                "seat_type": row["seat_type"],
                "college_code": row["college_code"],
                "college_name": row["college_name"],
                "course_name": row["course_name"],
                "category": row["category"],
                **{round_column(n): "" for n in rounds},
            }
        entry[round_column(int(row["round"]))] = row["closing_rank"]
    return list(wide.values()), rounds


def validate_wide(rows: List[dict], rounds: List[int]) -> List[str]:
    problems: List[str] = []
    columns = [round_column(n) for n in rounds]
    for row in rows:
        values = [row[c] for c in columns if row[c] != ""]
        if not values:
            problems.append(f"programme with no cut-off in any round: {row}")
        for raw in values:
            try:
                rank = float(raw)
            except ValueError:
                problems.append(f"non-numeric rank: {raw!r} in {row}")
                continue
            if rank <= 0:
                problems.append(f"non-positive rank: {raw!r} in {row}")
        if not re.fullmatch(r"[A-Z]\d{3}", row["college_code"]):
            problems.append(f"malformed college code: {row['college_code']}")
        if not row["course_name"] or len(row["course_name"]) < 3:
            problems.append(f"suspicious course name: {row['course_name']!r}")
    return problems


def validate(records: List[dict]) -> List[str]:
    problems: List[str] = []
    for row in records:
        try:
            rank = float(row["closing_rank"])
        except ValueError:
            problems.append(f"non-numeric rank: {row}")
            continue
        if rank <= 0:
            problems.append(f"non-positive rank: {row}")
        if not re.fullmatch(r"[A-Z]\d{3}", row["college_code"]):
            problems.append(f"malformed college code: {row['college_code']}")
        if not row["course_name"] or len(row["course_name"]) < 3:
            problems.append(f"suspicious course name: {row['course_name']!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report-only", action="store_true",
                        help="parse and validate but write no file")
    parser.add_argument("--keep-non-engineering", action="store_true",
                        help="retain architecture/design/planning programmes")
    args = parser.parse_args()

    if args.keep_non_engineering:
        global NON_ENGINEERING
        NON_ENGINEERING = re.compile(r"(?!)")  # never matches

    all_records: List[dict] = []
    totals = Stats()

    for source in SOURCES:
        path = RAW_DIR / source.filename
        if not path.exists():
            sys.exit(f"missing source PDF: {path}")
        stats = Stats()
        records = parse_pdf(path, source, stats)
        stats.rows = len(records)
        all_records.extend(records)

        print(
            f"{source.filename:26} round={source.round_no} "
            f"seat={source.seat_type:3} colleges={stats.colleges:3d} "
            f"rows={stats.rows:5d} fractional={stats.fractional:4d} "
            f"decimal-repairs={stats.decimal_repairs:3d} "
            f"name-joins={stats.name_joins:4d} "
            f"dropped-non-engg={stats.dropped_non_engineering:3d}"
        )
        for key in (
            "fractional", "decimal_repairs", "name_joins",
            "dropped_non_engineering", "off_grid", "college_name_wraps",
        ):
            setattr(totals, key, getattr(totals, key) + getattr(stats, key))
        totals.dropped_courses.update(stats.dropped_courses)

    canonicalise_courses(all_records, totals)
    before = len(all_records)
    all_records = dedupe(all_records, totals)

    print("\n--- totals ---")
    print(f"rows                 {len(all_records)} (deduped {before - len(all_records)})")
    print(f"fractional ranks     {totals.fractional}")
    print(f"decimal repairs      {totals.decimal_repairs}")
    print(f"wrapped-name joins   {totals.name_joins}")
    print(f"bracket-split fixes  {totals.bracket_repairs} rows")
    print(f"mid-word name fixes  {totals.name_repairs} rows, "
          f"{totals.name_variants} variants folded")
    print(f"college-name wraps   {totals.college_name_wraps}")
    print(f"off-grid values      {totals.off_grid}")
    print(f"non-engg cells drop  {totals.dropped_non_engineering}")
    if totals.dropped_courses:
        print("dropped programmes:")
        for name, count in sorted(totals.dropped_courses.items()):
            print(f"    {name}  (x{count})")

    by_round: Counter = Counter(
        (r["round"], r["seat_type"]) for r in all_records
    )
    print("\nrows by round/seat_type:")
    for key in sorted(by_round):
        print(f"    round {key[0]} {key[1]:3}  {by_round[key]:5d}")
    print(f"\ndistinct colleges    {len({r['college_code'] for r in all_records})}")
    print(f"distinct courses     {len({r['course_name'] for r in all_records})}")
    print(f"distinct categories  {len({r['category'] for r in all_records})}")

    problems = validate(all_records)
    if problems:
        print(f"\n!! {len(problems)} validation problems", file=sys.stderr)
        for problem in problems[:20]:
            print(f"   {problem}", file=sys.stderr)
        return 1

    wide_rows, rounds = pivot_rounds(all_records)
    print(f"\npivoted to one row per programme: {len(wide_rows)} rows, "
          f"round columns {[round_column(n) for n in rounds]}")
    filled = Counter()
    for row in wide_rows:
        for n in rounds:
            if row[round_column(n)] != "":
                filled[n] += 1
    for n in rounds:
        print(f"    {round_column(n):18} {filled[n]:6d} filled "
              f"({len(wide_rows) - filled[n]} blank)")

    problems = validate_wide(wide_rows, rounds)
    if problems:
        print(f"\n!! {len(problems)} validation problems", file=sys.stderr)
        for problem in problems[:20]:
            print(f"   {problem}", file=sys.stderr)
        return 1
    print("\nvalidation: clean")

    if args.report_only:
        print("(--report-only: nothing written)")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    all_records = wide_rows
    fields = [
        "exam_type", "year", "seat_type", "college_code",
        "college_name", "course_name", "category",
    ] + [round_column(n) for n in rounds]
    with open(args.out, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_records)
    try:
        shown = args.out.resolve().relative_to(REPO_ROOT)
    except ValueError:
        shown = args.out
    print(f"\nwrote {len(all_records)} rows -> {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
