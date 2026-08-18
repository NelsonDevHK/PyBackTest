import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from path_utils import get_data_dir


def load_data(symbol: str, timeframe: str, start_date: str, end_date: str):
    data_dir = get_data_dir()
    files = sorted(data_dir.glob(f"{symbol.lower()}_{timeframe.lower()}_*.csv"))

    if not files:
        raise FileNotFoundError(
            f"No {symbol} {timeframe} CSV files found in {data_dir}. "
            "Run fetch_twelvedata.py or fetch via MT5 first."
        )

    frames = []
    for csv_path in files:
        try:
            date_part = csv_path.stem.split("_")[-2]
        except IndexError:
            continue

        if start_date <= date_part <= end_date:
            df = pd.read_csv(csv_path)
            if "datetime" not in df.columns:
                continue
            df["datetime"] = pd.to_datetime(df["datetime"])
            frames.append(df)

    if not frames:
        raise FileNotFoundError(f"No data found for {symbol} from {start_date} to {end_date}.")

    combined = pd.concat(frames, ignore_index=True).sort_values("datetime")
    return combined


def plot_candles(df: pd.DataFrame, title: str):
    fig, ax = plt.subplots(figsize=(14, 6))

    x_positions = mdates.date2num(df["datetime"])
    width = 0.0022

    for x, open_price, high, low, close in zip(
        x_positions,
        df["open"],
        df["high"],
        df["low"],
        df["close"],
    ):
        color = "green" if close >= open_price else "red"
        ax.vlines(x, low, high, color=color, linewidth=1.0)
        ax.add_patch(
            Rectangle(
                (x - width / 2, min(open_price, close)),
                width,
                abs(close - open_price),
                facecolor=color,
                edgecolor=color,
                alpha=0.8,
            )
        )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    fig.autofmt_xdate()
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def parse_args():
    parser = argparse.ArgumentParser(description="Plot XAUUSD CFD candlestick data from CSV files")
    parser.add_argument("--symbol", default="GOLD", help="CSV symbol prefix, e.g. xauusd")
    parser.add_argument("--timeframe", default="m5", help="Timeframe tag in the filename, e.g. m5, h1")
    parser.add_argument("--start-date", default="2026-07-27", help="YYYY-MM-DD")
    parser.add_argument("--end-date", default="2026-07-31", help="YYYY-MM-DD")
    return parser.parse_args()


def main():
    args = parse_args()
    df = load_data(args.symbol, args.timeframe, args.start_date, args.end_date)
    plot_candles(df, f"{args.symbol.upper()} {args.timeframe.upper()} candlestick chart")


if __name__ == "__main__":
    main()