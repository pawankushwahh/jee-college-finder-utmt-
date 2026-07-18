"""
JEE Choice-Filtering Criteria Analyzer
========================================
Goal: figure out, from real data, what "closing_rank / student_rank" ratio
(or gap) should be used to cut off unrealistically-safe colleges — instead
of guessing a number like "5000 rank student shouldn't see rank-100 colleges".

WHAT YOU NEED TO PROVIDE
-------------------------
A CSV with historical counseling data, one row per (year, round, college,
branch, category, quota) with at least these columns:

    year          e.g. 2021, 2022, 2023, 2024
    round         counseling round number (last round is what matters most)
    college       college name or code
    branch        program/branch name
    category      GEN / OBC / SC / ST / EWS etc. (optional but useful)
    opening_rank  int
    closing_rank  int

This is exactly the shape of JoSAA's official "opening & closing rank"
data (published every year on josaa.nic.in), so it should be easy to get.

If you ALSO have actual student choice-filling data (a student's rank +
the list of colleges they filled as choices), point CHOICE_FILE to it too
— that lets us measure real behavior instead of inferring it. Format:

    student_rank, choice_number, college, branch, closing_rank_of_choice

HOW TO RUN
----------
    python3 analyze_criteria.py --ranks path/to/opening_closing_ranks.csv
    python3 analyze_criteria.py --ranks ranks.csv --choices choices.csv

WHAT IT OUTPUTS
----------------
1. Distribution of (closing_rank / opening_rank) — tells you how much a
   single college/branch's rank *band* naturally varies. A cutoff tighter
   than this is meaningless noise.
2. Year-over-year fluctuation of closing rank for the same college/branch
   — tells you how much "safety margin" is actually needed to be safe,
   as opposed to arbitrarily safe.
3. (If choices file given) Distribution of ratio = closing_rank / student_rank
   actually chosen by real students — the empirical basis for a cutoff.
4. Suggested cutoff ratios at multiple percentiles (e.g. "95% of real
   choices fall within 4.2x of the student's rank") so you can pick a
   defensible threshold rather than an arbitrary one.
"""

import argparse
import sys
import pandas as pd
import numpy as np


def load_ranks(path):
    df = pd.read_csv(path)
    required = {"year", "college", "branch", "opening_rank", "closing_rank"}
    missing = required - set(c.lower() for c in df.columns)
    if missing:
        sys.exit(f"ranks file missing required columns: {missing}")
    df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["opening_rank", "closing_rank"])
    df["opening_rank"] = pd.to_numeric(df["opening_rank"], errors="coerce")
    df["closing_rank"] = pd.to_numeric(df["closing_rank"], errors="coerce")
    df = df.dropna(subset=["opening_rank", "closing_rank"])
    return df


def load_choices(path):
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    required = {"student_rank", "closing_rank_of_choice"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"choices file missing required columns: {missing}")
    return df


def band_width_stats(df):
    """How wide is a single college/branch's own opening-closing band?
    A 'realistic choice' cutoff narrower than typical band width is noise."""
    d = df.copy()
    d = d[d["opening_rank"] > 0]
    d["band_ratio"] = d["closing_rank"] / d["opening_rank"]
    print("\n=== 1. Opening-to-closing band width (per college/branch/year) ===")
    print(d["band_ratio"].describe(percentiles=[.5, .75, .9, .95, .99]))
    return d


def yoy_fluctuation_stats(df):
    """How much does the SAME college/branch's closing rank move year to
    year? This tells you the natural noise floor for 'safety margin'."""
    d = df.copy()
    key = ["college", "branch"]
    if "category" in d.columns:
        key.append("category")
    pivot = d.groupby(key + ["year"])["closing_rank"].mean().reset_index()
    pivot = pivot.sort_values("year")

    fluct_ratios = []
    for _, g in pivot.groupby(key):
        g = g.sort_values("year")
        cr = g["closing_rank"].values
        if len(cr) < 2:
            continue
        ratios = cr[1:] / cr[:-1]
        fluct_ratios.extend(ratios[np.isfinite(ratios)])

    fluct_ratios = pd.Series(fluct_ratios)
    print("\n=== 2. Year-over-year closing-rank fluctuation ratio (yr_n / yr_n-1) ===")
    if len(fluct_ratios) == 0:
        print("Not enough multi-year data per college/branch to compute this.")
    else:
        print(fluct_ratios.describe(percentiles=[.05, .1, .25, .75, .9, .95]))
        print(
            "\nInterpretation: a ratio of 1.3 means closing rank moved up "
            "30% the following year purely from natural fluctuation. "
            "Your 'safe' cutoff margin should be at least this wide, or "
            "you risk mislabeling a real option as 'unrealistic'."
        )
    return fluct_ratios


def choice_ratio_stats(choices_df):
    """If we have real student choice data: the empirical distribution of
    closing_rank / student_rank actually chosen. This is the strongest
    evidence for where to draw the cutoff line."""
    d = choices_df.copy()
    d = d[d["student_rank"] > 0]
    d["ratio"] = d["closing_rank_of_choice"] / d["student_rank"]
    print("\n=== 3. Real student choices: closing_rank / student_rank ===")
    print(d["ratio"].describe(percentiles=[.5, .75, .9, .95, .99]))

    print("\nSuggested cutoff ratios by coverage:")
    for p in [0.80, 0.90, 0.95, 0.99]:
        val = d["ratio"].quantile(p)
        print(f"  {int(p*100)}% of real choices fall within {val:.2f}x of student's rank")
    return d


def suggest_segments(df, rank_points):
    """For a handful of sample student ranks, show what the college count
    looks like under different candidate cutoff ratios, so you can see the
    effect of each candidate rule before picking one."""
    print("\n=== 4. Effect of candidate cutoff ratios on option count ===")
    candidate_ratios = [2, 3, 5, 8, 12, 20]
    for rank in rank_points:
        print(f"\nStudent rank = {rank}")
        eligible = df[df["closing_rank"] >= rank]
        print(f"  All eligible (current method): {len(eligible)} rows")
        for ratio in candidate_ratios:
            capped = eligible[eligible["closing_rank"] <= rank * ratio]
            print(f"  Within {ratio}x cutoff (closing_rank <= {rank*ratio:>10,}): {len(capped)} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranks", required=True, help="CSV of opening/closing ranks")
    ap.add_argument("--choices", required=False, help="CSV of real student choice data")
    ap.add_argument(
        "--sample-ranks",
        type=int,
        nargs="+",
        default=[100, 1000, 5000, 20000, 50000, 100000],
        help="Sample student ranks to test candidate cutoffs against",
    )
    args = ap.parse_args()

    ranks_df = load_ranks(args.ranks)
    band_width_stats(ranks_df)
    yoy_fluctuation_stats(ranks_df)

    if args.choices:
        choices_df = load_choices(args.choices)
        choice_ratio_stats(choices_df)
    else:
        print(
            "\n(No --choices file given — skipping empirical student-behavior "
            "stats. This is the most reliable signal if you can get it.)"
        )

    suggest_segments(ranks_df, args.sample_ranks)

    print(
        "\n=== HOW TO USE THIS ===\n"
        "- If you have a --choices file: use the percentile table in section 3\n"
        "  directly. E.g. picking the 90th-percentile ratio means your filter\n"
        "  keeps 90% of what real students actually consider, and drops the\n"
        "  long tail of 'technically eligible but nobody picks it'.\n"
        "- If you don't have choice data: use section 2's fluctuation ratio as\n"
        "  a floor (don't cut tighter than natural year-to-year noise), then\n"
        "  pick a ratio from section 4 that gives a sane-looking option count\n"
        "  (e.g. 20-60 options for a mid-range rank feels 'browsable' vs 300).\n"
        "- Consider a NON-LINEAR cutoff: low ranks (top 1000) may need a wider\n"
        "  ratio (colleges are sparse and IITs cluster together) while high\n"
        "  ranks (100,000+) may need a much wider ratio too (colleges are\n"
        "  numerous but seats fill slowly). Check if section 4's output shows\n"
        "  this pattern before locking in one flat ratio for all ranks.\n"
    )


if __name__ == "__main__":
    main()