import pandas as pd
import numpy as np
import re
import json

def clean_rank(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.upper().endswith('P'):
        s = s[:-1].strip()
    try:
        return float(s)
    except ValueError:
        return None

def classify_inst_type(name):
    low = name.lower()
    if "indian institute of technology" in low and "information" not in low:
        return "IIT"
    if "iiit" in low or "indian institute of information" in low or "iiitm" in low or "iiitdm" in low:
        return "IIIT"
    if "national institute of technology" in low or "nit " in low or "nit," in low or low.startswith("nit "):
        return "NIT"
    return "GFTI"

def extract_branch(program):
    s = str(program).strip()
    match = re.match(r"^([^(]+)", s)
    if match:
        return match.group(1).strip()
    return s

def classify_branch_family(branch_clean):
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

def main():
    df = pd.read_csv("Data/jee_cutoff_last_round.csv")
    print("Initial Row Count:", len(df))
    
    # Basic cleaning
    df["Closing Rank"] = df["Closing Rank"].apply(clean_rank)
    df = df.dropna(subset=["Closing Rank"])
    print("Row Count with valid Closing Rank:", len(df))
    
    df["Institute_Type"] = df["Institute"].apply(classify_inst_type)
    df["Branch_Clean"] = df["Academic Program Name"].apply(extract_branch)
    df["Branch_Family"] = df["Branch_Clean"].apply(classify_branch_family)
    
    # Filter for OPEN, Gender-Neutral to make ranks comparable
    df_crl = df[
        (df["Seat Type"] == "OPEN") & 
        (df["Gender"].str.lower().str.contains("gender-neutral|neutral"))
    ]
    print("CRL Rows:", len(df_crl))
    
    # 1. Average closing rank by Institute Type and Year
    inst_type_year = df_crl.groupby(["Institute_Type", "Year"])["Closing Rank"].mean().reset_index()
    print("\n--- Inst Type Closing Rank by Year ---")
    print(inst_type_year)
    
    # 2. Top Branch Family trends
    branch_year = df_crl[df_crl["Branch_Family"] != "Others"].groupby(["Branch_Family", "Year"])["Closing Rank"].mean().reset_index()
    print("\n--- Branch Family Closing Rank by Year ---")
    print(branch_year)

    # 3. Top 5 competitive IITs trends
    top_iits = ["Indian Institute of Technology Bombay", 
                "Indian Institute of Technology Delhi", 
                "Indian Institute of Technology Madras",
                "Indian Institute of Technology Kanpur",
                "Indian Institute of Technology Kharagpur"]
    iit_trends = df_crl[df_crl["Institute"].isin(top_iits)].groupby(["Institute", "Year"])["Closing Rank"].mean().reset_index()
    print("\n--- Top IITs trends ---")
    print(iit_trends)

if __name__ == "__main__":
    main()
