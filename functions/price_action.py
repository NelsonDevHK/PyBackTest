from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

from path_utils import get_data_dir

base_dir = Path(__file__).resolve().parent.parent
data_dir = get_data_dir()

dates = ["2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31"]
weekdays = ["mon", "tue", "wed", "thu", "fri"]

frames = []
for date_str, weekday in zip(dates, weekdays):
    csv_path = data_dir / f"xau_usd_5min_{date_str}_{weekday}.csv"
    if not csv_path.exists():
        print(f"Missing file: {csv_path.name}")
        continue

    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")
    df["day"] = weekday
    frames.append(df)

if not frames:
    raise FileNotFoundError("No data files found for the requested date range.")

combined_df = pd.concat(frames, ignore_index=True)

fig, ax = plt.subplots(figsize=(14, 6))

x_positions = mdates.date2num(combined_df["datetime"])
width = 0.0022

for x, open_, high, low, close in zip(
    x_positions,
    combined_df["open"],
    combined_df["high"],
    combined_df["low"],
    combined_df["close"],
):
    color = "green" if close >= open_ else "red"
    ax.vlines(x, low, high, color=color, linewidth=1.0)
    ax.add_patch(Rectangle((x - width / 2, min(open_, close)), width, abs(close - open_),
                           facecolor=color, edgecolor=color, alpha=0.8))

ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
fig.autofmt_xdate()
ax.set_title("XAU/USD 5-minute candlestick chart from 2026-07-27 to 2026-07-31")
ax.set_xlabel("Time")
ax.set_ylabel("Price")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()