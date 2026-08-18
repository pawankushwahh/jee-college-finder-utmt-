"""Static configuration for the COMEDK recommendation engine.

Mirrors ``app/disha/config.py`` in structure: a ``Settings`` class holding all
engine-specific constants, and a module-level ``settings`` singleton.  The
object is deliberately separate from the JEE ``settings`` instance so that
tuning one engine cannot silently move the other.

Why COMEDK needs its own band constants
---------------------------------------
JoSAA publishes an **opening and a closing rank** per programme, so JEE can ask
a factual question: "did a student at your rank actually get a seat here last
year?"  The width of that opening-closing window is real data — median ~3,200
ranks in the JoSAA 2025 set.

COMEDK publishes a **single rank** (the closing rank of the last admitted
candidate).  The admitted band is therefore unobserved and has to be modelled.
Expressing it as a pure fraction of the cutoff — the first version of this
engine — breaks down at both ends of the rank range, because the same 15 %
means 104 ranks at a cutoff of 692 and 16,770 ranks at a cutoff of 111,800:

    rank      1  →  Target 0    Reach 0    Safe 459   (every option "Safe")
    rank 85,000  →  Target 100  Reach 87   Safe 108   (bucket explosion)
    rank 105,000 →  Target 74   Reach 141  Safe 0     (no backups at all)

So the band width is a fraction of the cutoff **clamped into an absolute
range**.  A clamped band keeps one interpretable meaning across the whole rank
range: "within roughly N ranks of the cutoff" rather than "within N % of it".

Constants after the move to all-rounds data — read this before tuning
---------------------------------------------------------------------
The engine now reads ``comedk_2025_all_rounds.csv`` and takes a programme's
cut-off as the MAX across the rounds it actually allotted in (see
``data_loader._resolve_rank``).  Two things changed, and only one of them is
about this file.

The *scale* barely moved.  The largest closing rank is still 111,800 and the
smallest still 692, because the rebuild added colleges and courses rather than
extending the rank range.  So every band and sigma ceiling below still sits
where it was measured and none of them moved.

The *distribution* moved a lot, for two compounding reasons: the dataset grew
from 637 rows to 1,114 (150 colleges instead of 101, 69 courses instead of 46),
and a round-4 cut-off is the loosest rank a programme ever admitted.  At GM
rank 76,983 the eligible split went 217/36/32 (Safe/Target/Reach) to
558/45/41 — Safe grew 2.6x while the dataset grew 1.75x.

That is a real consequence of the data change, not a bug: more of the published
record is now visible, and the most permissive rank actually admitted is a
looser boundary than round 1 alone.  Re-tuning the bands against the new
distribution is a deliberate product decision that belongs in its own change
with its own justification — not folded into the data swap, which is why
nothing below moved.  Setting ``round_strategy = 1`` reproduces the
round-1-only view if that comparison is wanted.
"""

from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"


class Settings:
    # The mock round, all four counselling rounds and the pre-counselling seat
    # matrix, built from the six official PDFs by
    # scripts/build_comedk_dataset.py — see docs/DATA_PIPELINE.md.
    csv_path: str = str(_DATA_DIR / "comedk_2025_all_rounds.csv")

    # ── Which round's cut-off to recommend against ────────────────────────
    # The dataset keeps every round; this picks the one number the recommender
    # compares a rank against.  "max" (highest rank admitted in any round) is
    # the default and mirrors JEE and KCET.  "last" / "first" / an int round
    # number are also accepted — see data_loader._resolve_rank, chiefly that a
    # fixed round number drops every programme that did not allot in it, and
    # that COMEDK's rounds are not category-symmetric (GM ran in rounds 1/3/4,
    # KKR only in rounds 1/2), so an int strategy empties one quota entirely.
    round_strategy: str = "max"

    # Sanity bound: reject any rank above this value as likely erroneous.
    # The largest closing rank anywhere in the rebuilt dataset is 111,800 —
    # unchanged from the previous CSV — so this ceiling still catches typos
    # (an extra trailing digit) without rejecting a genuine rank.
    max_rank: int = 200_000

    # ── Target band (the modelled admitted window) ───────────────────────
    # A programme is a Target when the student's rank sits inside
    # [cutoff - target_band, cutoff].  The band is
    # ``clamp(safe_margin * cutoff, target_band_floor, target_band_ceiling)``.
    #
    # safe_margin keeps the original 0.15 fraction.  The floor encodes the
    # honest reading of a single published cutoff: a programme closing at 692
    # admitted students from rank ~1 up to 692, so its real admitted band is at
    # least ~700 ranks wide, not the 104 ranks that 15 % would suggest.  The
    # ceiling stops the band from swallowing 17,000 ranks at the weak end of
    # the list, which is what previously produced 100-programme Target buckets.
    safe_margin: float = 0.15
    target_band_floor: float = 1_000.0
    target_band_ceiling: float = 6_000.0

    # ── Reach band (how far past a cutoff is still worth listing) ─────────
    # Keeps JEE's UPPER_MARGIN fraction, capped in absolute terms.  No floor:
    # at low cutoffs the multiplicative form is the honest one — a rank-2,000
    # student has no real chance at a programme that closed at 692, and a floor
    # would list it as a 0 %-probability "Dream".
    upper_margin: float = 0.25
    reach_band_ceiling: float = 8_000.0

    # ── Probability curve ────────────────────────────────────────────────
    # Stated prior, NOT a fitted value.  Only one year of COMEDK data exists in
    # this repo, so sigma_fraction cannot be estimated from year-over-year
    # cutoff movement.  A second year of data would let it be fitted per branch
    # family.  0.12 is a reasonable assumption: year-over-year drift is roughly
    # proportional to where the cutoff sits.
    #
    # sigma_ceiling exists for the same reason as reach_band_ceiling — an
    # unclamped sigma of 13,400 at cutoff 111,800 made a 6,800-rank cushion
    # read as only 79 % likely.
    sigma_fraction: float = 0.12
    sigma_floor: float = 150.0
    sigma_ceiling: float = 5_000.0
    steepness: float = 1.5      # same constant as JEE

    # ── Curation: how many cards each bucket shows by default ─────────────
    # Every programme the student is eligible for is still counted and still
    # reachable through the per-bucket views; these caps only bound the default
    # "all" response.  Without them a rank-1 student is handed 459 options and
    # a rank-85,000 student 295 — which is a data dump, not a recommendation.
    #
    # Nothing eligible is ever deleted: ordering plus a cap does the curation,
    # so there is still no lower-bound overqualification prune in this engine.
    cap_target: int = 30
    cap_reach: int = 20
    cap_safe: int = 25

    # Max programmes from a single institute inside one bucket's shown list.
    # Ordering by quality alone gave a rank-1 student six of ten cards from the
    # same college; the student wants a shortlist of colleges, not one college's
    # prospectus.  Relaxed automatically when a bucket cannot otherwise fill.
    max_per_institute: int = 2

    # ── Top-rank fallback ─────────────────────────────────────────────────
    # For students with exceptional ranks (≤ top_rank_threshold), every
    # programme is Safe and the three-bucket framing provides no signal.
    # In that case, show a curated shortlist of the top_rank_cap most
    # competitive programmes — mirroring JEE's _apply_top_rank_fallback().
    top_rank_threshold: int = 100
    top_rank_cap: int = 10

    # ── Quality score blend (used for ordering inside a bucket) ───────────
    # A programme's own cutoff percentile is the sharpest demand signal COMEDK
    # gives us; the institute's brand tier only has five distinct values, so it
    # acts as a mild prior rather than the primary key.
    weight_competitiveness: float = 0.70
    weight_brand: float = 0.30

    @property
    def resolved_csv_path(self) -> Path:
        return Path(self.csv_path)


settings = Settings()
