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
``kcet_2025_round1_cutoffs_cleaned.csv`` (18,850 rows, GM category) has:

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
"""

from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"


class Settings:
    # Path to the KCET 2025 round-1 cutoff CSV.
    csv_path: str = str(_DATA_DIR / "kcet_2025.csv")

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
    # Only one round of this dataset exists in the repo (round 1 only, no
    # Closing_R2..R6 to measure real movement), so sigma_fraction is a stated
    # prior — same situation and same value COMEDK used, since neither
    # dataset can be fitted from year-over-year movement yet.
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
