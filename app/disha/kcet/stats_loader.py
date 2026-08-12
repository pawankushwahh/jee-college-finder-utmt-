"""Statistical insights for the KCET dataset, served at /api/kcet/stats.

Output shape matches what templates/disha_templates/kcet/stats.html already
expects (data.summary, data.quota_counts, data.inst_competitiveness.KCET,
data.branch_popularity, data.highest_cutoffs, data.lowest_cutoffs) so the
existing stats page keeps working unchanged — only the data source
underneath moved from the old ad-hoc dict loader to data_loader.KcetProgram.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from .data_loader import load_programs

_EMPTY: Dict[str, Any] = {
    "summary": {
        "total_records": 0,
        "unique_institutes": 0,
        "unique_programs": 0,
        "unique_quotas": 0,
        "unique_seat_types": 0,
    },
    "quota_counts": {},
    "highest_cutoffs": [],
    "lowest_cutoffs": [],
    "inst_competitiveness": {},
    "branch_popularity": [],
    "branch_counts": {},
    "round_averages": {},
}


def compute_kcet_stats() -> Dict[str, Any]:
    programs = load_programs()
    if not programs:
        return _EMPTY

    df = pd.DataFrame(
        {
            "institute": p.institute,
            "program": p.program,
            "quota": p.seat_category,
            "cutoff_rank": p.closing_rank,
        }
        for p in programs
    )

    unique_institutes = int(df["institute"].nunique())
    unique_programs = int(df["program"].nunique())
    unique_quotas = sorted(df["quota"].unique().tolist())
    quota_counts = df["quota"].value_counts().to_dict()

    ref_quota = "GM" if "GM" in df["quota"].values else (unique_quotas[0] if unique_quotas else "")
    comp_df = df[df["quota"] == ref_quota].copy() if ref_quota else df.copy()

    highest_cutoffs = []
    lowest_cutoffs = []
    if not comp_df.empty:
        for _, row in comp_df.nsmallest(10, "cutoff_rank").iterrows():
            highest_cutoffs.append(
                {
                    "institute": row["institute"],
                    "program": row["program"],
                    "quota": row["quota"],
                    "closing_rank": int(row["cutoff_rank"]),
                    "inst_type": "KCET",
                }
            )
        for _, row in comp_df.nlargest(10, "cutoff_rank").iterrows():
            lowest_cutoffs.append(
                {
                    "institute": row["institute"],
                    "program": row["program"],
                    "quota": row["quota"],
                    "closing_rank": int(row["cutoff_rank"]),
                    "inst_type": "KCET",
                }
            )

    inst_competitiveness: Dict[str, list] = {"KCET": []}
    if not comp_df.empty:
        grouped = (
            comp_df.groupby("institute")
            .agg(avg_closing=("cutoff_rank", "mean"), min_closing=("cutoff_rank", "min"), total_programs=("program", "count"))
            .reset_index()
            .sort_values("avg_closing")
        )
        for _, row in grouped.head(15).iterrows():
            inst_competitiveness["KCET"].append(
                {
                    "institute": row["institute"],
                    "avg_closing_rank": round(float(row["avg_closing"]), 1),
                    "min_opening_rank": int(row["min_closing"]),
                    "total_programs": int(row["total_programs"]),
                }
            )

    branch_popularity = []
    if not comp_df.empty:
        branch_pop = (
            comp_df.groupby("program")
            .agg(avg_closing=("cutoff_rank", "mean"), count=("institute", "count"))
            .reset_index()
        )
        filtered = branch_pop[branch_pop["count"] >= 3]
        if filtered.empty:
            filtered = branch_pop
        for _, row in filtered.sort_values("avg_closing").head(15).iterrows():
            branch_popularity.append(
                {
                    "branch": row["program"],
                    "avg_closing_rank": round(float(row["avg_closing"]), 1),
                    "total_programs": int(row["count"]),
                }
            )

    return {
        "summary": {
            "total_records": len(programs),
            "unique_institutes": unique_institutes,
            "unique_programs": unique_programs,
            "unique_quotas": len(unique_quotas),
            "unique_seat_types": len(unique_quotas),
        },
        "quota_counts": quota_counts,
        "highest_cutoffs": highest_cutoffs,
        "lowest_cutoffs": lowest_cutoffs,
        "inst_competitiveness": inst_competitiveness,
        "branch_popularity": branch_popularity,
        "branch_counts": {},
        "round_averages": {},
    }
