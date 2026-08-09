from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

csv_path = Path(__file__).resolve().parent / "5MinutesData" / "xau_usd_5min_2026-07-29.csv"

df = pd.read_csv(csv_path)
df["datetime"] = pd.to_datetime(df["datetime"])
df = df.sort_values("datetime")

plt.figure(figsize=(12, 5))
plt.plot(df["datetime"], df["close"], color="royalblue", linewidth=1.2)
plt.title("XAU/USD 5-minute close price")
plt.xlabel("Time")
plt.ylabel("Price")
plt.tight_layout()
plt.show()