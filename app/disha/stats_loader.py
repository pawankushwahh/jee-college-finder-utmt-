from __future__ import annotations

import re
import pandas as pd
from typing import Dict, List, Any
from .config import settings

def _classify_institute_type(name: str) -> str:
    low = name.lower()
    if "indian institute of technology" in low and "information" not in low:
        return "IIT"
    if "iiit" in low or "indian institute of information" in low or "iiitm" in low or "iiitdm" in low:
        return "IIIT"
    if "national institute of technology" in low or "nit " in low or "nit," in low or low.startswith("nit "):
        return "NIT"
    return "GFTI"

def _clean_rank_value(val: Any) -> float | None:
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    # Strip 'P' suffix for preparatory ranks if any
    if s.upper().endswith('P'):
        s = s[:-1].strip()
    try:
        return float(s)
    except ValueError:
        return None

def _classify_branch_family(branch_clean: str) -> str:
    low = branch_clean.lower()
    if any(x in low for x in ["computer", "information", "artificial", "data science", "software", "computing"]):
        return "Computer Science & IT"
    if any(x in low for x in ["electrical", "electronic", "instrumentation", "telecommunication", "communication"]):
        return "Electrical & Electronics"
    if any(x in low for x in ["mechanical", "production", "aerospace", "manufacturing", "industrial", "automobile"]):
        return "Mechanical & Production"
    if any(x in low for x in ["civil", "architecture", "planning", "environmental"]):
        return "Civil & Architecture"
    if any(x in low for x in ["chemical", "materials", "metallurgical", "metallurgy", "polymer", "ceramic", "textile", "mining"]):
        return "Chemical & Materials"
    return "Others"

def compute_dataset_stats() -> Dict[str, Any]:
    """Load settings.resolved_basic_merged_data_path and compute statistical insights."""
    csv_path = settings.resolved_basic_merged_data_path
    df = pd.read_csv(csv_path)

    # Clean the primary key columns
    df["Institute"] = df["Institute"].fillna("").astype(str).str.strip()
    df["Academic Program Name"] = df["Academic Program Name"].fillna("").astype(str).str.strip()
    df["Quota"] = df["Quota"].fillna("").astype(str).str.strip()
    df["Seat Type"] = df["Seat Type"].fillna("").astype(str).str.strip()
    df["Gender"] = df["Gender"].fillna("").astype(str).str.strip()

    total_records = len(df)
    unique_institutes = int(df["Institute"].nunique())
    unique_programs = int(df["Academic Program Name"].nunique())
    unique_quotas = df["Quota"].unique().tolist()
    unique_seat_types = df["Seat Type"].unique().tolist()
    unique_genders = df["Gender"].unique().tolist()

    # Classify Institute Types
    df["Institute_Type"] = df["Institute"].apply(_classify_institute_type)
    inst_type_counts = df["Institute_Type"].value_counts().to_dict()

    # State-wise distribution of programs
    from . import states
    df["State"] = df["Institute"].apply(states.get_institute_state)
    state_counts = df["State"].value_counts().to_dict()

    # Round-wise closing rank columns
    closing_cols = [f"Closing_R{i}" for i in range(1, 7) if f"Closing_R{i}" in df.columns]
    opening_cols = [f"Opening_R{i}" for i in range(1, 7) if f"Opening_R{i}" in df.columns]

    # Calculate clean closing ranks per round
    round_averages = {}
    for col in closing_cols:
        clean_col = df[col].apply(_clean_rank_value)
        mean_val = clean_col.mean()
        round_averages[col] = float(mean_val) if not pd.isna(mean_val) else None

    # Calculate overall opening and closing ranks for each row to compute min/max
    df_clean_open = pd.DataFrame({col: df[col].apply(_clean_rank_value) for col in opening_cols})
    df_clean_close = pd.DataFrame({col: df[col].apply(_clean_rank_value) for col in closing_cols})

    df["Min_Opening"] = df_clean_open.min(axis=1)
    df["Max_Closing"] = df_clean_close.max(axis=1)

    # Filter out records without valid cutoffs for rank statistics
    valid_cutoffs = df.dropna(subset=["Min_Opening", "Max_Closing"])

    # Filter for OPEN, Gender-Neutral to get actual CRL rank
    crl_cutoffs = valid_cutoffs[
        (valid_cutoffs["Seat Type"] == "OPEN") & 
        (valid_cutoffs["Gender"].str.lower().str.contains("gender-neutral|neutral"))
    ]

    highest_cutoffs = []
    if not crl_cutoffs.empty:
        top_competitive = crl_cutoffs.nsmallest(10, "Max_Closing")
        for _, row in top_competitive.iterrows():
            highest_cutoffs.append({
                "institute": row["Institute"],
                "program": row["Academic Program Name"],
                "quota": row["Quota"],
                "gender": row["Gender"],
                "opening_rank": int(row["Min_Opening"]),
                "closing_rank": int(row["Max_Closing"]),
                "inst_type": row["Institute_Type"]
            })

    lowest_cutoffs = []
    if not crl_cutoffs.empty:
        least_competitive = crl_cutoffs.nlargest(10, "Max_Closing")
        for _, row in least_competitive.iterrows():
            lowest_cutoffs.append({
                "institute": row["Institute"],
                "program": row["Academic Program Name"],
                "quota": row["Quota"],
                "gender": row["Gender"],
                "opening_rank": int(row["Min_Opening"]),
                "closing_rank": int(row["Max_Closing"]),
                "inst_type": row["Institute_Type"]
            })

    # Quota and Seat Type distribution
    quota_counts = df["Quota"].value_counts().to_dict()
    seat_type_counts = df["Seat Type"].value_counts().to_dict()
    gender_counts = df["Gender"].value_counts().to_dict()

    # Institute Competitiveness (Average closing rank of OPEN, Gender-Neutral programs)
    inst_competitiveness = []
    if not crl_cutoffs.empty:
        grouped = crl_cutoffs.groupby("Institute").agg(
            avg_closing=("Max_Closing", "mean"),
            min_opening=("Min_Opening", "min"),
            total_programs=("Academic Program Name", "count")
        ).reset_index()
        grouped = grouped.sort_values("avg_closing")
        for _, row in grouped.head(15).iterrows():
            inst_competitiveness.append({
                "institute": row["Institute"],
                "avg_closing_rank": round(row["avg_closing"], 1),
                "min_opening_rank": int(row["min_opening"]),
                "total_programs": int(row["total_programs"]),
                "inst_type": _classify_institute_type(row["Institute"])
            })

    # Popular Branches
    def _extract_branch_name(program: str) -> str:
        s = str(program).strip()
        match = re.match(r"^([^(]+)", s)
        if match:
            return match.group(1).strip()
        return s

    df["Branch_Clean"] = df["Academic Program Name"].apply(_extract_branch_name)
    branch_counts = df["Branch_Clean"].value_counts().to_dict()

    popular_branches = []
    if not crl_cutoffs.empty:
        crl_cutoffs_copy = crl_cutoffs.copy()
        crl_cutoffs_copy["Branch_Clean"] = crl_cutoffs_copy["Academic Program Name"].apply(_extract_branch_name)
        branch_grouped = crl_cutoffs_copy.groupby("Branch_Clean").agg(
            avg_closing=("Max_Closing", "mean"),
            total_seats=("Branch_Clean", "count")
        ).reset_index()
        branch_grouped = branch_grouped[branch_grouped["total_seats"] >= 5]
        branch_grouped = branch_grouped.sort_values("avg_closing")
        for _, row in branch_grouped.head(15).iterrows():
            popular_branches.append({
                "branch": row["Branch_Clean"],
                "avg_closing_rank": round(row["avg_closing"], 1),
                "total_programs": int(row["total_seats"])
            })

    # Volatility summary from data_loader
    from .data_loader import load_programs_basic
    programs = load_programs_basic()
    volatility_counts = {}
    for p in programs:
        tag = p.volatility_tag
        volatility_counts[tag] = volatility_counts.get(tag, 0) + 1

    # 1. Gender Advantage Analysis
    gender_advantage = []
    gender_df = valid_cutoffs[["Institute", "Academic Program Name", "Quota", "Seat Type", "Gender", "Max_Closing", "Institute_Type"]].copy()
    pivot_gender = gender_df.pivot_table(
        index=["Institute", "Academic Program Name", "Quota", "Seat Type", "Institute_Type"],
        columns="Gender",
        values="Max_Closing"
    ).reset_index()
    neutral_col = [c for c in pivot_gender.columns if "neutral" in c.lower()]
    female_col = [c for c in pivot_gender.columns if "female" in c.lower()]
    if neutral_col and female_col:
        neutral_name = neutral_col[0]
        female_name = female_col[0]
        pivot_gender = pivot_gender.dropna(subset=[neutral_name, female_name])
        if not pivot_gender.empty:
            pivot_gender["ratio"] = pivot_gender[female_name] / pivot_gender[neutral_name]
            pivot_gender["diff"] = pivot_gender[female_name] - pivot_gender[neutral_name]
            grouped_gender = pivot_gender.groupby("Institute_Type").agg(
                avg_ratio=("ratio", "mean"),
                avg_diff=("diff", "mean")
            ).reset_index()
            for _, row in grouped_gender.iterrows():
                gender_advantage.append({
                    "inst_type": row["Institute_Type"],
                    "avg_multiplier": round(row["avg_ratio"], 3),
                    "avg_rank_difference": round(row["avg_diff"], 1)
                })

    # 2. CSE Cutoff Premium by Institute Type
    cse_premium = []
    if not crl_cutoffs.empty:
        crl_copy = crl_cutoffs.copy()
        crl_copy["Branch_Clean"] = crl_copy["Academic Program Name"].apply(_extract_branch_name)
        crl_copy["Family"] = crl_copy["Branch_Clean"].apply(_classify_branch_family)
        for itype in ["IIT", "NIT", "IIIT", "GFTI"]:
            itype_df = crl_copy[crl_copy["Institute_Type"] == itype]
            if itype_df.empty:
                continue
            cse_df = itype_df[itype_df["Family"] == "Computer Science & IT"]
            non_cse_df = itype_df[itype_df["Family"] != "Computer Science & IT"]
            cse_avg = round(cse_df["Max_Closing"].mean(), 1) if not cse_df.empty else None
            non_cse_avg = round(non_cse_df["Max_Closing"].mean(), 1) if not non_cse_df.empty else None
            overall_avg = round(itype_df["Max_Closing"].mean(), 1)
            cse_premium.append({
                "inst_type": itype,
                "cse_avg": cse_avg,
                "non_cse_avg": non_cse_avg,
                "overall_avg": overall_avg,
                "cse_programs": len(cse_df),
                "non_cse_programs": len(non_cse_df)
            })

    # 3. Top 5 Competitive Branches per Institute Type
    top_branches_by_type = {}
    if not crl_cutoffs.empty:
        crl_br = crl_cutoffs.copy()
        crl_br["Branch_Clean"] = crl_br["Academic Program Name"].apply(_extract_branch_name)
        for itype in ["IIT", "NIT", "IIIT"]:
            itype_df = crl_br[crl_br["Institute_Type"] == itype]
            if itype_df.empty:
                continue
            branch_avg = itype_df.groupby("Branch_Clean").agg(
                avg_closing=("Max_Closing", "mean"),
                count=("Branch_Clean", "count")
            ).reset_index()
            branch_avg = branch_avg[branch_avg["count"] >= 3]  # min 3 programs
            branch_avg = branch_avg.sort_values("avg_closing").head(5)
            entries = []
            for _, row in branch_avg.iterrows():
                entries.append({
                    "branch": row["Branch_Clean"],
                    "avg_closing": round(row["avg_closing"], 1),
                    "count": int(row["count"])
                })
            top_branches_by_type[itype] = entries

    # 4. 4-Year vs 5-Year Program Comparison
    duration_comparison = []
    dur_df = valid_cutoffs[
        (valid_cutoffs["Seat Type"] == "OPEN") &
        (valid_cutoffs["Gender"].str.lower().str.contains("gender-neutral|neutral"))
    ][["Institute_Type", "Academic Program Name", "Max_Closing"]].copy()
    def _classify_duration(program_name: str) -> str:
        name = program_name.lower()
        if "5 years" in name or "dual" in name or "integrated" in name:
            return "5-Year Dual/Integrated"
        return "4-Year B.Tech"
    dur_df["Duration"] = dur_df["Academic Program Name"].apply(_classify_duration)
    grouped_dur = dur_df.groupby(["Institute_Type", "Duration"]).agg(
        avg_closing=("Max_Closing", "mean"),
        program_count=("Max_Closing", "count")
    ).reset_index()
    for itype in ["IIT", "NIT", "IIIT", "GFTI"]:
        itype_rows = grouped_dur[grouped_dur["Institute_Type"] == itype]
        four_year_avg = None
        five_year_avg = None
        four_count = 0
        five_count = 0
        row_4 = itype_rows[itype_rows["Duration"] == "4-Year B.Tech"]
        if not row_4.empty:
            four_year_avg = round(row_4.iloc[0]["avg_closing"], 1)
            four_count = int(row_4.iloc[0]["program_count"])
        row_5 = itype_rows[itype_rows["Duration"] == "5-Year Dual/Integrated"]
        if not row_5.empty:
            five_year_avg = round(row_5.iloc[0]["avg_closing"], 1)
            five_count = int(row_5.iloc[0]["program_count"])
        duration_comparison.append({
            "inst_type": itype,
            "four_year_avg": four_year_avg,
            "four_year_count": four_count,
            "five_year_avg": five_year_avg,
            "five_year_count": five_count
        })

    # 5. Options/Colleges Available by Rank (capped for cleaner display)
    MAX_DISPLAY_PROGRAMS = 20
    MAX_DISPLAY_INSTITUTES = 15

    advanced_curve = []
    adv_thresholds = [500, 1000, 2000, 5000, 8000, 10000, 15000, 20000, 25000]
    iit_crl = valid_cutoffs[
        (valid_cutoffs["Institute_Type"] == "IIT") &
        (valid_cutoffs["Seat Type"] == "OPEN") &
        (valid_cutoffs["Gender"].str.lower().str.contains("gender-neutral|neutral"))
    ]
    for r in adv_thresholds:
        available_rows = iit_crl[iit_crl["Max_Closing"] >= r]
        total_progs = len(available_rows)
        total_insts = int(available_rows["Institute"].nunique())
        advanced_curve.append({
            "rank": r,
            "program_count": min(total_progs, MAX_DISPLAY_PROGRAMS),
            "institute_count": min(total_insts, MAX_DISPLAY_INSTITUTES),
            "total_programs": total_progs,
            "total_institutes": total_insts
        })

    mains_curve = []
    mains_thresholds = [5000, 10000, 20000, 30000, 50000, 75000, 100000, 150000, 200000]
    mains_crl = valid_cutoffs[
        (valid_cutoffs["Institute_Type"] != "IIT") &
        (valid_cutoffs["Seat Type"] == "OPEN") &
        (valid_cutoffs["Gender"].str.lower().str.contains("gender-neutral|neutral"))
    ]
    for r in mains_thresholds:
        available_rows = mains_crl[mains_crl["Max_Closing"] >= r]
        total_progs = len(available_rows)
        total_insts = int(available_rows["Institute"].nunique())
        mains_curve.append({
            "rank": r,
            "program_count": min(total_progs, MAX_DISPLAY_PROGRAMS),
            "institute_count": min(total_insts, MAX_DISPLAY_INSTITUTES),
            "total_programs": total_progs,
            "total_institutes": total_insts
        })

    return {
        "summary": {
            "total_records": total_records,
            "unique_institutes": unique_institutes,
            "unique_programs": unique_programs,
            "unique_quotas": len(unique_quotas),
            "unique_seat_types": len(unique_seat_types),
            "unique_genders": len(unique_genders)
        },
        "inst_type_counts": inst_type_counts,
        "state_counts": state_counts,
        "quota_counts": quota_counts,
        "seat_type_counts": seat_type_counts,
        "gender_counts": gender_counts,
        "round_averages": round_averages,
        "highest_cutoffs": highest_cutoffs,
        "lowest_cutoffs": lowest_cutoffs,
        "inst_competitiveness": inst_competitiveness,
        "popular_branches": popular_branches,
        "branch_counts": dict(list(branch_counts.items())[:15]),
        "volatility_counts": volatility_counts,
        "gender_advantage": gender_advantage,
        "cse_premium": cse_premium,
        "top_branches_by_type": top_branches_by_type,
        "duration_comparison": duration_comparison,
        "rank_availability": {
            "advanced": advanced_curve,
            "mains": mains_curve
        }
    }

