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
"""

from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"


class Settings:
    # Path to the COMEDK cutoff CSV.
    csv_path: str = str(_DATA_DIR / "comedk_2025.csv")

    # Sanity bound: reject any rank above this value as likely erroneous.
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
