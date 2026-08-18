"""Round-wise cut-offs, and how they collapse into the one number a rank is
compared against.

Counselling is not a single event. KEA runs three rounds, COMEDK four (plus a
mock), and a programme publishes a cut-off only for the rounds it actually
allotted a seat in. Both exams therefore store the complete published record —
one column per round — and pick a single number at load time. Both had grown
their own copy of that picking logic, character-identical apart from the
docstring; this is that logic, once.

What is genuinely shared here is *mechanism*: how to find the round columns,
how to read a number out of a CSV cell, and what "max"/"last"/"first"/round-N
mean. What each exam does with the result is not shared, because the exams'
counselling rules differ in ways that matter:

* **COMEDK's rounds are not category-symmetric.** GM ran in rounds 1, 3 and 4
  while KKR ran only in rounds 1 and 2, so a GM ``max`` is taken over three
  rounds and a KKR ``max`` over two. Anything comparing the two pools (the KKR
  gap) is comparing across that boundary — see ``comedk/data_loader.py``.
* **COMEDK publishes a mock round.** It allotted no seat, so it must never be
  selectable as "the" cut-off. :data:`ROUND_COLUMN` does not match it by
  construction, and COMEDK exposes it separately as ``mock_rank``.
* **KCET keeps the round range, not just the collapsed number.** Its bucketing
  reads the tough and loose ends off the rounds directly, and imputes a band for
  the 26% of programmes that published only one round — a KCET-specific rule
  living in ``kcet/data_loader.py``.

JEE is deliberately not a caller. Its loader is a pandas merge that collapses
``Closing_R1…R6`` with a vectorised column-wise max; routing it through these
per-row helpers would be slower and would not share a single line of reasoning.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple, TypeVar

# ── Strategies ─────────────────────────────────────────────────────────────
# How a programme's several round-wise cut-offs collapse into one number.
STRATEGY_MAX = "max"    # highest rank admitted in any round — the default
STRATEGY_LAST = "last"  # the last round the programme appears in
STRATEGY_FIRST = "first"

DEFAULT_ROUND_STRATEGY = STRATEGY_MAX

# Per-round cut-off columns are discovered from the CSV header rather than
# hardcoded, so a year with an extra round needs no loader change — only a
# rebuilt CSV.
#
# The pattern deliberately does not match ``closing_rank_mock``: COMEDK's mock
# round is a simulation published before counselling opened and allotted no
# seat, so it must never be selectable as a cut-off.
ROUND_COLUMN = re.compile(r"^closing_rank_r(\d+)$")


def parse_number(value: Optional[str]) -> Optional[float]:
    """Read a CSV cell as a float, or None if it is blank or unparseable.

    Float rather than int because KEA publishes fractional cut-offs (76553.5,
    15223.875) — an earlier KCET loader coerced these with ``int(float(v))`` and
    silently truncated 2,366 of them.

    Thousands separators are stripped. Neither committed dataset currently
    contains one (verified: zero numeric cells with a comma in either file), but
    the source PDFs print them, so a rebuild that preserves them parses rather
    than silently dropping the row.
    """
    if value is None:
        return None
    text = value.strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Optional[str]) -> Optional[int]:
    """As :func:`parse_number`, truncated to an int.

    For genuinely integral columns — seat counts and fees — not for ranks.
    """
    number = parse_number(value)
    return None if number is None else int(number)


def round_columns(
    fieldnames: Optional[Sequence[str]], pattern: re.Pattern = ROUND_COLUMN
) -> List[Tuple[str, int]]:
    """The CSV's per-round cut-off columns, as ``(column, round)``, by round."""
    found: List[Tuple[str, int]] = []
    for name in fieldnames or []:
        match = pattern.match((name or "").strip())
        if match:
            found.append((name, int(match.group(1))))
    return sorted(found, key=lambda pair: pair[1])


def ranks_by_round(
    row: Mapping[str, Optional[str]], columns: Sequence[Tuple[str, int]]
) -> Dict[int, float]:
    """Every cut-off one CSV row published, keyed by round number.

    A blank cell means the programme allotted no seat that round, so it is
    absent from the result rather than present as a zero — "no cut-off" and "a
    cut-off of 0" are different statements, and only the first one is ever true
    of this data.

    Callers apply their own validity rules on top. COMEDK additionally drops
    non-positive values as a vacancy signal; that rule stays in its loader
    because it is a statement about COMEDK's published record, not about how
    rounds work.
    """
    found: Dict[int, float] = {}
    for column, round_no in columns:
        rank = parse_number(row.get(column))
        if rank is not None:
            found[round_no] = rank
    return found


def resolve_rank(by_round: Dict[int, float], strategy: object) -> Optional[float]:
    """Pick the single cut-off the recommender compares a rank against.

    ``strategy`` is ``"max"``, ``"last"``, ``"first"``, or an ``int`` round
    number. An int returns None when the programme published nothing that round
    — it genuinely had no cut-off then, so it must drop out of that view rather
    than borrow a neighbouring round's number.

    Why ``max`` is the default, for both exams:

    * *Coverage.* Cut-offs exist per round only for programmes that allotted a
      seat that round. KCET's round 3 covers 13,599 of 24,495 keys; COMEDK's
      round 4 covers 325 of 1,126. ``max`` and ``last`` keep every key; a fixed
      round number does not, by design.
    * *Semantics.* Cut-offs loosen as counselling proceeds (KCET: round 3 >=
      round 1 for 99.5% of keys present in both; COMEDK: 91% of GM keys closed
      later in round 4, median +28,291), so the maximum is the most permissive
      rank actually admitted — the boundary a student is asking about. It also
      matches the JEE loader's ``Closing Rank = MAX across Closing_R1…R6``.

    ``bool`` is excluded from the int branch on purpose: ``True`` is an ``int``
    in Python, and "round True" is a bug, not a request for round 1.
    """
    if not by_round:
        return None
    if isinstance(strategy, int) and not isinstance(strategy, bool):
        return by_round.get(strategy)
    if strategy == STRATEGY_LAST:
        return by_round[max(by_round)]
    if strategy == STRATEGY_FIRST:
        return by_round[min(by_round)]
    return max(by_round.values())


View = TypeVar("View")


class StrategyCache:
    """One built view per round strategy, built on first use.

    The default view is built once and reused; asking for a round-specific view
    ("what would round 1 alone have said?") costs one extra build the first time
    and is then cached too. Identity is part of the contract — callers rely on
    ``load(x) is load(x)`` — so a view is never rebuilt while the process lives.

    ``default_strategy`` is a callable rather than a value because the exam's
    ``settings.round_strategy`` is read at call time: reading it once at import
    would freeze whatever the module happened to see first and make the setting
    untestable.
    """

    def __init__(
        self,
        build: Callable[[object], View],
        default_strategy: Callable[[], object],
    ) -> None:
        self._build = build
        self._default_strategy = default_strategy
        self._views: Dict[object, View] = {}

    def get(self, strategy: object = None) -> View:
        key = strategy if strategy is not None else self._default_strategy()
        # `is None` rather than a truth test: a view can legitimately be empty
        # (a missing data file logs and returns []), and rebuilding it on every
        # call would turn one logged error into one per request.
        view = self._views.get(key)
        if view is None:
            view = self._views[key] = self._build(key)
        return view

    def clear(self) -> None:
        """Drop every built view. For tests that change the data or settings."""
        self._views.clear()
