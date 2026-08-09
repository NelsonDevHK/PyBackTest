import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from twelvedata import TDClient

from path_utils import get_data_dir, load_project_env

load_project_env()


def file_name_for_day(date_value):
    dt = datetime.fromisoformat(date_value)
    weekday = dt.strftime('%a').lower()
    return f"xau_usd_5min_{date_value}_{weekday}.csv"


# Command line usage example:
# python fetch_missing_day.py 2026-08-05 2026-08-06 2026-08-07

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch one or more days of 5-minute XAU/USD data")
    parser.add_argument("dates", nargs="+", help="Dates to fetch in YYYY-MM-DD format")
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = get_data_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")
    if not TWELVE_DATA_API_KEY:
        raise ValueError("Missing TWELVE_DATA_API_KEY in .env")

    client = TDClient(apikey=TWELVE_DATA_API_KEY)

    for missing_day in args.dates:
        start_dt = datetime.fromisoformat(missing_day + " 00:00:00")
        end_dt = start_dt + timedelta(days=1)
        output_path = output_dir / file_name_for_day(missing_day)

        print("missing_day:", missing_day)
        print("start_dt:", start_dt)
        print("end_dt:", end_dt)

        ts = client.time_series(
            symbol="XAU/USD",
            interval="5min",
            start_date=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            outputsize=5000,
            timezone="UTC",
        )

        df = ts.as_pandas()
        if "datetime" not in df.columns:
            df = df.reset_index()
            if "index" in df.columns:
                df = df.rename(columns={"index": "datetime"})
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.sort_values("datetime", ascending=True).reset_index(drop=True)
        df.to_csv(output_path, index=False)

        print(f"Saved missing-day data to: {output_path}")


if __name__ == "__main__":
    main()
