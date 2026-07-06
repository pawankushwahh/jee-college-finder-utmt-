import sys
sys.path.append("/Users/pawankushwah/Library/Python/3.9/lib/python/site-packages")
import pandas as pd
df = pd.read_csv("app/disha/data/josaa_merged_2025.csv")
print("Columns:")
print(df.columns.tolist())
print("\nShape:", df.shape)
print("\nUnique values for some columns:")
for col in ["Institute", "Quota", "Seat Type", "Gender"]:
    if col in df.columns:
        print(f"{col}: {df[col].nunique()} unique values")
print("\nFirst 3 rows:")
print(df.head(3).to_string())
