import pandas as pd
import re

df = pd.read_csv("app/body_quest/data/josaa_merged_2025.csv")
df["cr"] = pd.to_numeric(df["Closing_R6"], errors="coerce")
crl = df[(df["Seat Type"] == "OPEN") & (df["Gender"].str.contains("Neutral", case=False, na=False))]

def classify_cse(name):
    low = name.lower()
    if "computer science" not in low and "cse" not in low and "information technology" not in low:
        return None
    if "information technology" in low:
        return "Information Technology"
    if any(x in low for x in ["artificial intelligence", " ai ", "ai)", "machine learning", " ml"]):
        return "CSE (AI / ML)"
    if any(x in low for x in ["data science", "data analytics", "analytics"]):
        return "CSE (Data Science)"
    if any(x in low for x in ["cyber", "security", "blockchain", "block chain"]):
        return "CSE (Cyber Security)"
    if any(x in low for x in ["dual degree", "5 years", "integrated", "mba"]):
        return "CSE (Dual / 5-Year)"
    # Check for other specializations in parentheses
    specs = re.findall(r"\(([^()]*)\)", name)
    for s in specs:
        sl = s.lower()
        if "4 year" in sl or "bachelor" in sl or "b.tech" in sl or "hons" in sl:
            continue
        if len(s) > 5:
            return "CSE (Other Specialization)"
    if "computer science" in low or "cse" in low:
        return "CSE (Core 4-Year)"
    return "CSE (Other)"

crl = crl.copy()
crl["cse_type"] = crl["Academic Program Name"].apply(classify_cse)
cse_only = crl[crl["cse_type"].notna()].copy()
grouped = cse_only.groupby("cse_type").agg(
    avg_closing=("cr", "mean"),
    count=("cr", "count")
).reset_index().sort_values("avg_closing")

print("=== CSE VARIANT CUTOFF ANALYSIS (OPEN, Gender-Neutral, 2025) ===")
for _, r in grouped.iterrows():
    print(f"  {r['cse_type']:30s}  avg_closing={r['avg_closing']:,.0f}  programs={int(r['count'])}")

# Also break by institute type
print("\n=== IIT ONLY ===")
def get_itype(inst):
    low = inst.lower()
    if "indian institute of technology" in low and "information" not in low:
        return "IIT"
    return "Other"

cse_only["itype"] = cse_only["Institute"].apply(get_itype)
iit_cse = cse_only[cse_only["itype"] == "IIT"]
grouped2 = iit_cse.groupby("cse_type").agg(
    avg_closing=("cr", "mean"),
    count=("cr", "count")
).reset_index().sort_values("avg_closing")
for _, r in grouped2.iterrows():
    print(f"  {r['cse_type']:30s}  avg_closing={r['avg_closing']:,.0f}  programs={int(r['count'])}")
