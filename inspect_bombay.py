import pandas as pd
df = pd.read_csv("Data/jee_cutoff_last_round.csv")
bombay_df = df[df["Institute"].str.contains("Bombay|BOMBAY", case=False, na=False)]
print("Bombay unique institute names:")
print(bombay_df["Institute"].unique())

print("\nBombay years represented:")
print(bombay_df["Year"].value_counts())

print("\nBombay in 2023 details:")
bombay_2023 = bombay_df[bombay_df["Year"] == 2023]
print("Rows for Bombay in 2023:", len(bombay_2023))
if len(bombay_2023) > 0:
    print("Unique Seat Types:", bombay_2023["Seat Type"].unique())
    print("Unique Genders:", bombay_2023["Gender"].unique())
    print("Unique Quotas:", bombay_2023["Quota"].unique())
    print("Sample rows:")
    print(bombay_2023.head(3).to_string())
