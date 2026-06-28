"""
clean_jee_cutoff.py
-------------------
Filters JEE/JoSAA cutoff CSV to keep only the LAST ROUND entry
for each unique (Institute, Academic Program Name, Quota, Seat Type, Gender, Year).

Usage:
    python clean_jee_cutoff.py input.csv output.csv

If no arguments are given, it looks for 'jee_cutoff.csv' in the current directory
and writes 'jee_cutoff_last_round.csv'.
"""

import sys
import pandas as pd

# ── File paths ────────────────────────────────────────────────────────────────
input_file  = sys.argv[1] if len(sys.argv) > 1 else "merged_jee_cutoff_2018_2025.csv"
output_file = sys.argv[2] if len(sys.argv) > 2 else "jee_cutoff_last_round.csv"

# ── Load ──────────────────────────────────────────────────────────────────────
print(f"Reading: {input_file}")
df = pd.read_csv(input_file)
print(f"  Loaded {len(df):,} rows, {df['Year'].nunique()} years, "
      f"rounds: {sorted(df['Round'].unique())}")

# ── Clean up whitespace in string columns ─────────────────────────────────────
str_cols = df.select_dtypes(include="object").columns
df[str_cols] = df[str_cols].apply(lambda c: c.str.strip())

# ── Ensure Round and Year are numeric ─────────────────────────────────────────
df["Round"] = pd.to_numeric(df["Round"], errors="coerce")
df["Year"]  = pd.to_numeric(df["Year"],  errors="coerce")

# ── Group keys ────────────────────────────────────────────────────────────────
GROUP_KEYS = [
    "Institute",
    "Academic Program Name",
    "Quota",
    "Seat Type",
    "Gender",
    "Year",
]

# ── Keep only the last (highest) round per group ──────────────────────────────
# Sort so the last round ends up at the bottom of each group, then deduplicate
df_sorted = df.sort_values(GROUP_KEYS + ["Round"])
df_last   = df_sorted.drop_duplicates(subset=GROUP_KEYS, keep="last")

print(f"  After filtering → {len(df_last):,} rows "
      f"({len(df) - len(df_last):,} duplicate-round rows removed)")

# ── Save ──────────────────────────────────────────────────────────────────────
df_last.to_csv(output_file, index=False)
print(f"Saved: {output_file}")

# ── Quick sanity check ────────────────────────────────────────────────────────
print("\nRound distribution in output (should ideally be the highest round per year):")
print(df_last.groupby(["Year", "Round"]).size().rename("rows").reset_index().to_string(index=False))