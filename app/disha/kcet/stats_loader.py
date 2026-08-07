from __future__ import annotations

import pandas as pd
from typing import Dict, List, Any
from .data_loader import get_programs

def compute_kcet_stats() -> Dict[str, Any]:
    """Compute statistical insights for KCET 2025 dataset."""
    programs = get_programs()
    if not programs:
        return {
            "summary": {
                "total_records": 0,
                "unique_institutes": 0,
                "unique_programs": 0,
                "unique_quotas": 0,
                "unique_seat_types": 0
            },
            "quota_counts": {},
            "highest_cutoffs": [],
            "lowest_cutoffs": [],
            "inst_competitiveness": {},
            "branch_popularity": [],
            "branch_counts": {},
            "round_averages": {},
            "round_averages_main": {},
            "round_averages_adv": {}
        }

    df = pd.DataFrame(programs)

    unique_institutes = int(df["institute"].nunique())
    unique_programs = int(df["program"].nunique())
    unique_quotas = df["quota"].unique().tolist()
    quota_counts = df["quota"].value_counts().to_dict()

    # Determine dominant/preferred quota to calculate competitiveness metrics.
    # For KCET, "GM" is General Merit. Fall back to the most common quota if GM is not present.
    ref_quota = "GM"
    if ref_quota not in df["quota"].values:
        if len(unique_quotas) > 0:
            ref_quota = df["quota"].value_counts().index[0]
        else:
            ref_quota = ""

    comp_df = df[df["quota"] == ref_quota].copy() if ref_quota else df.copy()

    highest_cutoffs = []
    lowest_cutoffs = []
    
    if not comp_df.empty:
        # Highest cutoffs (lowest numerical rank values)
        top_competitive = comp_df.nsmallest(10, "cutoff_rank")
        for _, row in top_competitive.iterrows():
            highest_cutoffs.append({
                "institute": row["institute"],
                "program": row["program"],
                "quota": row.get("quota", "GM"),
                "closing_rank": int(row["cutoff_rank"]),
                "inst_type": "KCET"
            })

        # Lowest cutoffs (highest numerical rank values)
        least_competitive = comp_df.nlargest(10, "cutoff_rank")
        for _, row in least_competitive.iterrows():
            lowest_cutoffs.append({
                "institute": row["institute"],
                "program": row["program"],
                "quota": row.get("quota", "GM"),
                "closing_rank": int(row["cutoff_rank"]),
                "inst_type": "KCET"
            })

    # Institute Competitiveness - Grouped by institute
    inst_competitiveness = {}
    if not comp_df.empty:
        grouped = comp_df.groupby("institute").agg(
            avg_closing=("cutoff_rank", "mean"),
            min_closing=("cutoff_rank", "min"),
            total_programs=("program", "count")
        ).reset_index()
        grouped = grouped.sort_values("avg_closing")
        
        entries = []
        for _, row in grouped.head(15).iterrows():
            entries.append({
                "institute": row["institute"],
                "avg_closing_rank": round(row["avg_closing"], 1),
                "min_opening_rank": int(row["min_closing"]),
                "total_programs": int(row["total_programs"])
            })
        inst_competitiveness["KCET"] = entries

    # Branch popularity / competitiveness
    branch_popularity = []
    if not comp_df.empty:
        branch_pop = comp_df.groupby("program").agg(
            avg_closing=("cutoff_rank", "mean"),
            count=("institute", "count")
        ).reset_index()
        # Consider branches offered by at least 3 colleges
        filtered_branch_pop = branch_pop[branch_pop["count"] >= 3]
        if filtered_branch_pop.empty:
            filtered_branch_pop = branch_pop
        
        filtered_branch_pop = filtered_branch_pop.sort_values("avg_closing").head(15)
        
        for _, row in filtered_branch_pop.iterrows():
            branch_popularity.append({
                "branch": row["program"],
                "avg_closing_rank": round(row["avg_closing"], 1),
                "total_programs": int(row["count"])
            })

    return {
        "summary": {
            "total_records": len(programs),
            "unique_institutes": unique_institutes,
            "unique_programs": unique_programs,
            "unique_quotas": len(unique_quotas),
            "unique_seat_types": 0
        },
        "quota_counts": quota_counts,
        "highest_cutoffs": highest_cutoffs,
        "lowest_cutoffs": lowest_cutoffs,
        "inst_competitiveness": inst_competitiveness,
        "branch_popularity": branch_popularity,
        "branch_counts": {},
        "round_averages": {},
        "round_averages_main": {},
        "round_averages_adv": {}
    }
