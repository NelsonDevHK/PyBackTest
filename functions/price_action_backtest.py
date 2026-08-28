import argparse
from pathlib import Path
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
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
        date_part = csv_path.stem.split("_")[-2]
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

def OneHour_df(df: pd.DataFrame, title: str = ""):
    df = df.copy().set_index("datetime")
    df_1h = df.resample("1h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"
    }).dropna().reset_index()
    return df_1h

def get_support_resistance(
    df: pd.DataFrame,
    zone_threshold: float = 5.0,
    reaction_candles: int = 10,
    min_touches: int = 2,
    formation_days: int = 3,
):
    """Build a channel from strong H1 reactions to initial support/resistance zones."""
    hourly_df = OneHour_df(df)
    first_day = hourly_df["datetime"].dt.normalize().min()
    formation_end = first_day + pd.Timedelta(days=formation_days)
    formation_df = hourly_df[hourly_df["datetime"] < formation_end].reset_index(drop=True)
    prices = formation_df["close"].astype(float).reset_index(drop=True)
    highs = formation_df["high"].astype(float).reset_index(drop=True)
    lows = formation_df["low"].astype(float).reset_index(drop=True)
    zone_step = zone_threshold * 2
    first_level = int(lows.min() // zone_step) * zone_step
    last_level = int(highs.max() // zone_step + 1) * zone_step
    zones = {
        center: {
            "center": center,
            "support_touches": 0,
            "resistance_touches": 0,
            "support_retests": 0,
            "resistance_retests": 0,
        }
        for center in range(int(first_level), int(last_level) + 1, int(zone_step))
    }

    for zone in zones.values():
        in_zone = (lows <= zone["center"] + zone_threshold) & (highs >= zone["center"] - zone_threshold)
        entries = in_zone & ~in_zone.shift(1, fill_value=False)

        for index in prices.index[entries]:
            future = prices.iloc[index + 1:index + 1 + reaction_candles]
            moved_up = (future >= zone["center"] + zone_threshold).any()
            moved_down = (future <= zone["center"] - zone_threshold).any()

            if moved_up and not moved_down:
                zone["support_touches"] += 1
                departure_index = index + 1 + int((future >= zone["center"] + zone_threshold).to_numpy().argmax())
                later = formation_df.iloc[departure_index + 1:]
                if ((later["low"] <= zone["center"] + zone_threshold) & (later["high"] >= zone["center"] - zone_threshold)).any():
                    zone["support_retests"] += 1
            elif moved_down and not moved_up:
                zone["resistance_touches"] += 1
                departure_index = index + 1 + int((future <= zone["center"] - zone_threshold).to_numpy().argmax())
                later = formation_df.iloc[departure_index + 1:]
                if ((later["low"] <= zone["center"] + zone_threshold) & (later["high"] >= zone["center"] - zone_threshold)).any():
                    zone["resistance_retests"] += 1

    price_range = prices.max() - prices.min()
    support_limit = prices.min() + price_range * 0.25
    resistance_limit = prices.max() - price_range * 0.25
    support_zones = [
        zone
        for zone in zones.values()
        if zone["center"] <= support_limit and zone["support_touches"] >= min_touches
    ]
    resistance_zones = [
        zone
        for zone in zones.values()
        if zone["center"] >= resistance_limit and zone["resistance_touches"] >= min_touches
    ]

    support = max(
        support_zones,
        key=lambda zone: (zone["support_retests"], zone["support_touches"], -zone["center"]),
        default=None,
    )
    resistance = max(
        resistance_zones,
        key=lambda zone: (zone["resistance_retests"], zone["resistance_touches"], zone["center"]),
        default=None,
    )

    if support is None or resistance is None:
        return None

    full_prices = hourly_df["close"].astype(float).reset_index(drop=True)
    full_highs = hourly_df["high"].astype(float).reset_index(drop=True)
    full_lows = hourly_df["low"].astype(float).reset_index(drop=True)
    support_points = []
    resistance_points = []

    for index in range(len(hourly_df) - 1):
        future = full_prices.iloc[index + 1:index + 1 + reaction_candles]
        if (
            full_highs.iloc[index] >= resistance["center"] - zone_threshold
            and (future <= full_highs.iloc[index] - zone_threshold).any()
            and (not resistance_points or index - resistance_points[-1][0] > reaction_candles)
        ):
            resistance_points.append((index, full_highs.iloc[index]))
        if (
            full_lows.iloc[index] <= support["center"] + zone_threshold
            and (future >= full_lows.iloc[index] + zone_threshold).any()
            and (not support_points or index - support_points[-1][0] > reaction_candles)
        ):
            support_points.append((index, full_lows.iloc[index]))

    if len(resistance_points) < 2 or not support_points:
        return None

    upper_x1, upper_y1 = resistance_points[0]
    upper_x2, upper_y2 = resistance_points[1]
    lower_x1, lower_y1 = support_points[0]
    slope = (upper_y2 - upper_y1) / (upper_x2 - upper_x1)
    upper_line = upper_y1 + slope * (np.arange(len(hourly_df)) - upper_x1)
    lower_line = lower_y1 + slope * (np.arange(len(hourly_df)) - lower_x1)
    upper_hits = ((full_highs - upper_line).abs() <= zone_threshold).sum()
    lower_hits = ((full_lows - lower_line).abs() <= zone_threshold).sum()

    if np.any(upper_line <= lower_line) or upper_hits < 2 or lower_hits < 2:
        return None

    if abs(slope) <= zone_threshold / 10:
        structure = "sideway_channel"
    elif slope > 0:
        structure = "accend_channel"
    else:
        structure = "deccend_channel"

    return {
        "x": hourly_df["datetime"].tolist(),
        "upper": upper_line,
        "lower": lower_line,
        "upper_touches": int(upper_hits),
        "lower_touches": int(lower_hits),
        "structure": structure,
    }


def plot_candles(df: pd.DataFrame, title: str):
    fig, ax = plt.subplots(figsize=(14, 6), facecolor="black")
    ax.set_facecolor("black")

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

    channel = get_support_resistance(df)
    structure = channel["structure"] if channel is not None else "no_channel"

    print(f"Trend: {'sideway' if channel is not None else 'no_channel'} ({structure})")

    if channel is not None:
        channel_x = mdates.date2num(channel["x"])
        channel_upper = channel["upper"]
        channel_lower = channel["lower"]
        ax.plot(channel_x, channel_upper, color="white", linewidth=1.2, label="H1 channel")
        ax.plot(channel_x, channel_lower, color="white", linewidth=1.2)
        print(
            f"Channel: drawn in white ({structure}, "
            f"upper touches={channel['upper_touches']}, lower touches={channel['lower_touches']})"
        )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    fig.autofmt_xdate()
    ax.set_title(f"{title} | {'sideway' if channel is not None else 'no_channel'} ({structure})", color="white")
    ax.set_xlabel("Time", color="white")
    ax.set_ylabel("Price", color="white")
    ax.tick_params(colors="white")
    ax.grid(True, color="gray", alpha=0.3)
    for spine in ax.spines.values():
        spine.set_color("gray")
    if channel is not None:
        ax.legend()
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