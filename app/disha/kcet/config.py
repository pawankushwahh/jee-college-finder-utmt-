"""Static configuration for the KCET recommendation engine.

Mirrors the structure of ``app/disha/comedk/config.py`` (a ``Settings`` class
+ module-level ``settings`` singleton), because KCET's data has the same shape
COMEDK's does: a single published closing rank per (college, course,
category) row, not an opening-closing window like JoSAA. The banding
methodology below is therefore COMEDK's — a fraction of the cutoff, clamped
into an absolute range — but every constant is measured fresh from this
dataset's own distribution, not copied from COMEDK's.

Why KCET needs its own numbers, not COMEDK's
----------------------------------------------
The round-1-only dataset these constants were measured from (18,850 rows, GM
category) had:

    p1    2,204      p50   67,328      p95  163,004
    p25  38,246      p75  101,524      p99  195,999
                      p90  141,150      max 249,733

COMEDK's own Closing_R1 (637 rows) has p50 76,983 / p75 96,996 / max 111,800 —
almost the same shape through the 75th percentile, but KCET's tail runs to
roughly 2.2x COMEDK's maximum (249,733 vs 111,800), because this dataset
carries ~30x more rows across 200 colleges and 24 reservation/region category
codes. Reusing COMEDK's absolute ceilings as-is would make every KCET option
past the ~90th percentile look like it sits right at the ceiling. The band
and sigma ceilings below are COMEDK's numbers scaled up by that measured
tail ratio; everything else (the fractions themselves, the floor reasoning)
follows the same logic COMEDK's config.py documents.

Constants after the move to all-rounds data — read this before tuning
---------------------------------------------------------------------
The engine now takes a programme's cut-off as the MAX across rounds 1-3 (see
``data_loader._load_raw_rows``). That barely moves the statistic these ceilings
were derived from — the GM maximum went 249,733 -> 262,158, a 5% shift, so the
tail-ratio scaling above still holds and the constants are left unchanged.

It moves the *middle* of the distribution enormously, because a programme's
round-3 cut-off is the loosest rank it ever admitted:

    p25  38,246 ->  54,994      p75  101,524 -> 247,460
    p50  67,328 -> 128,953      max  249,733 -> 262,158

The bands are absolute (13k/18k) against cut-offs whose median has roughly
doubled, so proportionally far more programmes now land in Safe and the
Safe/Target/Reach split discriminates less than it did on round-1 data. That is
a real consequence of the data change, not a bug, and re-tuning the bands is a
deliberate product decision that belongs in its own change with its own
justification — not folded into the data swap, which is why nothing below moved.
"""

from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"


class Settings:
    # All three KEA rounds, both seat pools. Built from the official cut-off
    # PDFs by scripts/build_kcet_dataset.py — see docs/DATA_PIPELINE.md.
    csv_path: str = str(_DATA_DIR / "kcet_2025_all_rounds.csv")

    # ── Which round's cut-off to recommend against ────────────────────────
    # The dataset keeps every round; this picks the one number the recommender
    # compares a rank against. "max" (highest rank admitted in any round) is the
    # default and mirrors JEE. "last" / "first" / an int round number are also
    # accepted — see data_loader._resolve_rank for the trade-offs, chiefly that
    # a fixed round number drops every programme that did not allot in it.
    round_strategy: str = "max"

    # ── Observed-range bucketing ──────────────────────────────────────────
    # A programme's bucket comes from the range of ranks KEA actually admitted
    # across the rounds, not from a synthetic band:
    #
    #     rank <= rank_low            Safe    (clears even the toughest round)
    #     rank_low < rank <= rank_high  Target  (admitted in some later round)
    #     rank > rank_high            Dream   (admitted in no round)
    #
    # This replaced a modelled target band of 15% of the cutoff clamped to
    # 13,000. Measured against the real admitted range, that band was 4.1x too
    # narrow at cutoffs of 120k-200k and 8.1x too narrow above 200k (the flat
    # ceiling stopped growing while the real range kept widening), and ~2x too
    # wide below 5,000. That mis-scaling, more than anything else, is why
    # 84-99% of every result set used to land in Safe.
    use_observed_range: bool = True

    # 26% of programmes appear in only one round, so they have no observed
    # range. 95% of those publish only a round-1 value, which is the *tight*
    # end -- so the band is imputed UPWARD from it. Treating the known value as
    # the loose end instead would mislabel genuinely-Safe students as Target.
    #
    # Ratios are the measured median of (high/low - 1) for multi-round
    # programmes in the same low-end bracket. Dispersion inside a bracket is
    # wide (p25-p75 spans roughly 3x), so an imputed band is a coarse estimate,
    # not a measurement -- programmes carrying one are flagged `band_imputed`
    # so callers can treat them with less confidence. The burden is very uneven:
    # 4% of GM rows need it versus 54-62% of some 371(j) categories.
    band_imputation_ratios: tuple = (
        (5_000, 0.51),
        (20_000, 0.41),
        (60_000, 0.44),
        (120_000, 0.56),
        (200_000, 0.30),
        (float("inf"), 0.01),
    )

    # Extra slack below rank_low before a programme stops being Target.
    #
    # Deliberately 0.0. A rank just below 2025's toughest round might still miss
    # 2026's, so some slack is defensible in principle -- but its correct width
    # is year-over-year drift, which **cannot be measured from a single year**.
    # Within-year round movement (median +28.8% from R1 to R2) measures the
    # applicant pool shrinking as seats are taken, not a new cohort arriving,
    # so it is the wrong quantity and is not used as a stand-in. Left at 0 so
    # the buckets mean exactly what the data shows; raise it only as an
    # explicit, stated safety margin.
    safe_buffer_fraction: float = 0.0

    # ── Relevance floor ───────────────────────────────────────────────────
    # Observed ranges fix *which* bucket, but not whether an option is worth
    # showing at all: a weak programme's own range is ~105,000 wide, so it
    # would qualify as Safe for every rank. Without a floor a rank-100 student
    # opening "Safe" received 1,576 options running out to cutoff 262,158 at
    # "100.0% probability".
    #
    # Cut at 4 sigma below the tough end, i.e. ~99.75% admission probability at
    # the current steepness: past that an option is a certainty and cannot
    # change which seat the student ends up with. Sigma here is the *relevance*
    # scale, deliberately separate from the probability sigma below -- one
    # number cannot serve both jobs, which is what produced "100.0%" on a
    # programme 2,600x below the student's rank.
    relevance_ceiling_z: float = 4.0
    relevance_sigma_fraction: float = 0.12
    relevance_sigma_floor: float = 300.0
    relevance_sigma_ceiling: float = 11_000.0

    # The window alone leaves a top-rank student only ~5 options, too few to
    # build a preference list from, so it never trims below this many.
    min_options: int = 25

    # Sanity bound: reject any rank above this value as likely erroneous.
    # Measured max closing rank in the GM category is 249,733; a generous
    # round-number ceiling above that avoids rejecting a genuine low-GM-rank
    # student while still catching typos (e.g. an extra trailing digit).
    max_rank: int = 400_000

    # ── Target band (the modelled admitted window) ───────────────────────
    # A programme is a Target when the student's rank sits inside
    # [cutoff - target_band, cutoff], where
    # target_band = clamp(safe_margin * cutoff, target_band_floor, target_band_ceiling).
    safe_margin: float = 0.15
    target_band_floor: float = 1_500.0
    target_band_ceiling: float = 13_000.0

    # ── Reach band (how far past a cutoff is still worth listing) ─────────
    # No floor, same reasoning as COMEDK: a rank-2,000 student has no real
    # chance at a programme that closed at 2,204, and a floor would list it
    # as a 0%-probability "Dream" anyway.
    upper_margin: float = 0.25
    reach_band_ceiling: float = 18_000.0

    # ── Probability curve ────────────────────────────────────────────────
    # sigma_fraction is still a stated prior, same value COMEDK used. It was
    # originally justified by "only round 1 exists, so movement cannot be
    # measured" — that is no longer true: the dataset now carries all three
    # rounds and every programme keeps its round-wise history in
    # KcetProgram.closing_rank_by_round, so round-to-round movement *is*
    # measurable and sigma could be fitted from it the way JEE's is. Nobody has
    # done that fitting yet, so the prior stands rather than being presented as
    # something derived from this data.
    sigma_fraction: float = 0.12
    sigma_floor: float = 300.0
    sigma_ceiling: float = 11_000.0
    steepness: float = 1.5  # same constant as JEE and COMEDK

    # ── Curation: how many cards each bucket shows by default ─────────────
    # Kept identical to the JEE engine's caps (Target 25 / Reach 15 / Safe
    # 15 = 55 shown) for product consistency: a student comparing JEE and
    # KCET results should see similarly sized shortlists, not an engine-
    # specific surprise. Every eligible programme is still counted and still
    # reachable through the per-bucket view.
    cap_target: int = 25
    cap_reach: int = 15
    cap_safe: int = 15

    # Max programmes from a single college inside one bucket's shown list.
    # Rows per college average ~7.9 here (max 59), so without a cap a single
    # large college could fill an entire bucket on its own.
    max_per_institute: int = 2

    # ── Top-rank mode ─────────────────────────────────────────────────────
    # Mirrors JEE's: triggered by bucket counts (Target==0 and Reach==0), not
    # a hardcoded rank, so it adapts to whichever category the student picks
    # (GM's low end starts around rank 234; a reserved category's low end
    # sits at a different rank entirely).
    top_rank_cap: int = 25

    @property
    def resolved_csv_path(self) -> Path:
        return Path(self.csv_path)


settings = Settings()
