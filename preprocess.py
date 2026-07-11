"""
Loads sales data for training/forecasting.

NOTE: This used to pull from MySQL (see db_connect.py), but the project
now works directly off sales_data.csv, so the DB dependency has been
removed. db_connect.py / load_data.py are kept only in case you want to
go back to a DB-backed setup later - they are not used by this file.
"""

import pandas as pd

CSV_PATH = "sales_data.csv"


def fetch_data():
    df = pd.read_csv(CSV_PATH)

    # Normalize column names -> date, product, region, sales
    df.columns = [c.strip().lower() for c in df.columns]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df = df.dropna(subset=["date", "sales"])

    # Multiple rows can share a date (different product/region) -
    # aggregate to one total-sales-per-day series for the trend model.
    daily = (
        df.groupby("date", as_index=False)["sales"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )

    print("Rows loaded from CSV:", df.shape[0])
    print("Distinct days after aggregation:", daily.shape[0])
    print(daily.head())

    return daily
