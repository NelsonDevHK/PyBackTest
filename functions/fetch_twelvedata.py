import os
import pandas as pd
from twelvedata import TDClient
from pathlib import Path
from datetime import datetime, timedelta

from path_utils import get_data_dir, load_project_env

load_project_env()


def file_name_for_day(date_value):
    dt = datetime.fromisoformat(date_value)
    weekday = dt.strftime('%a').lower()
    return f"xau_usd_5min_{date_value}_{weekday}.csv"


output_dir = get_data_dir()
output_dir.mkdir(parents=True, exist_ok=True)

#Access the API key from the environment variable
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

if not TWELVE_DATA_API_KEY:
	raise ValueError("Missing TWELVE_DATA_API_KEY in .env")

td = TDClient(apikey=TWELVE_DATA_API_KEY)

# Get yesterday in local time so date boundaries match your local calendar
target_day = (datetime.now().date() - timedelta(days=1)).strftime('%Y-%m-%d')
# target_day = "2026-07-29"
start_dt = datetime.fromisoformat(target_day + " 00:00:00")
end_dt = start_dt + timedelta(days=1)
output_path = output_dir / file_name_for_day(target_day)

print("target_day:", target_day)
print("start_dt:", start_dt)
print("end_dt:", end_dt)

ts = td.time_series(
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

print(f"Gold data successfully saved locally: {output_path}")