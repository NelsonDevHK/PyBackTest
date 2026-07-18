import os
from twelvedata import TDClient
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta

load_dotenv()

output_dir = Path(__file__).resolve().parent.parent / "15MinutesData"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "xau_usd_5min.csv"

#Access the API key from the environment variable
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

td = TDClient(apikey=TWELVE_DATA_API_KEY)

# Get latest price for XAU/USD
target_day = "2026-07-15"
start_dt = datetime.fromisoformat(target_day + " 00:00:00")
end_dt = start_dt + timedelta(days=1)

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