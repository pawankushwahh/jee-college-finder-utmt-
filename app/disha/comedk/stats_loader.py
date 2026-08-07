from __future__ import annotations

import pandas as pd
from typing import Dict, List, Any
from .data_loader import get_programs

def compute_comedk_stats() -> Dict[str, Any]:
    """Compute statistical insights for COMEDK 2025 dataset."""
    programs = get_programs()
    if not programs:
        return {}

    df = pd.DataFrame(programs)

    unique_institutes = int(df["institute"].nunique())
    unique_programs = int(df["program"].nunique())
    unique_quotas = df["quota"].unique().tolist()
    quota_counts = df["quota"].value_counts().to_dict()

    # Filter for General Merit to calculate competitiveness metrics
    gm_df = df[df["quota"] == "GM"].copy()

    highest_cutoffs = []
    lowest_cutoffs = []
    
    if not gm_df.empty:
        # Highest cutoffs (lowest numerical rank values)
        top_competitive = gm_df.nsmallest(10, "cutoff_rank")
        for _, row in top_competitive.iterrows():
            highest_cutoffs.append({
                "institute": row["institute"],
                "program": row["program"],
                "quota": row["quota"],
                "closing_rank": int(row["cutoff_rank"]),
                "inst_type": "COMEDK"
            })

        # Lowest cutoffs (highest numerical rank values)
        least_competitive = gm_df.nlargest(10, "cutoff_rank")
        for _, row in least_competitive.iterrows():
            lowest_cutoffs.append({
                "institute": row["institute"],
                "program": row["program"],
                "quota": row["quota"],
                "closing_rank": int(row["cutoff_rank"]),
                "inst_type": "COMEDK"
            })

    # Institute Competitiveness - Grouped by institute (using GM data)
    inst_competitiveness = {}
    if not gm_df.empty:
        grouped = gm_df.groupby("institute").agg(
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
                "min_opening_rank": int(row["min_closing"]), # UI uses this key for display
                "total_programs": int(row["total_programs"])
            })
        inst_competitiveness["COMEDK"] = entries

    # Branch popularity / competitiveness
    branch_popularity = []
    if not gm_df.empty:
        branch_pop = gm_df.groupby("program").agg(
            avg_closing=("cutoff_rank", "mean"),
            count=("institute", "count")
        ).reset_index()
        # Only consider branches offered by at least 3 colleges
        branch_pop = branch_pop[branch_pop["count"] >= 3].sort_values("avg_closing").head(15)
        
        for _, row in branch_pop.iterrows():
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
