import os
from twelvedata import TDClient
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta

load_dotenv()

output_dir = Path(__file__).resolve().parent / "5MinutesData"
output_dir.mkdir(parents=True, exist_ok=True)

#Access the API key from the environment variable
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

if not TWELVE_DATA_API_KEY:
	raise ValueError("Missing TWELVE_DATA_API_KEY in .env")

td = TDClient(apikey=TWELVE_DATA_API_KEY)

# Get yesterday in local time so date boundaries match your local calendar
target_day = (datetime.now().date() - timedelta(days=1)).strftime('%Y-%m-%d')
start_dt = datetime.fromisoformat(target_day + " 00:00:00")
end_dt = start_dt + timedelta(days=1)
output_path = output_dir / f"xau_usd_5min_{target_day}.csv"

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
df.to_csv(output_path)

print(f"Gold data successfully saved locally: {output_path}")