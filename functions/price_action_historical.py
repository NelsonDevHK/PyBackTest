import argparse
from datetime import date, datetime, time, timedelta, timezone

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

import MetaTrader5 as mt5

from fetch_mt5 import TIMEFRAME_MAP, connect_to_mt5, normalize_symbol
from price_action_logic import get_channel


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def load_mt5_data(symbol: str, timeframe: str, start_date: date, end_date: date) -> pd.DataFrame:
    timeframe_key = timeframe.lower()
    if timeframe_key not in TIMEFRAME_MAP:
        raise ValueError(f"Unsupported timeframe: {timeframe}. Use one of {sorted(TIMEFRAME_MAP)}")

    symbol_name = normalize_symbol(symbol)
    if not mt5.symbol_select(symbol_name, True):
        raise RuntimeError(f"MT5 could not select symbol '{symbol_name}': {mt5.last_error()}")

    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    rates = mt5.copy_rates_range(symbol_name, TIMEFRAME_MAP[timeframe_key], start_dt, end_dt)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No MT5 data returned for {symbol_name} from {start_date} to {end_date}")

    df = pd.DataFrame(rates)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    df = df[(df["datetime"] >= start_dt.replace(tzinfo=None)) & (df["datetime"] < end_dt.replace(tzinfo=None))]
    return df.sort_values("datetime").reset_index(drop=True)


def plot_candles(df: pd.DataFrame, symbol: str, timeframe: str, start_date: date, end_date: date):
    fig, ax = plt.subplots(figsize=(14, 6), facecolor="black")
    ax.set_facecolor("black")
    x_positions = mdates.date2num(df["datetime"])
    width = 0.0022

    for x, open_price, high, low, close in zip(
        x_positions, df["open"], df["high"], df["low"], df["close"]
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

    channel = get_channel(df)
    support = channel["support"] if isinstance(channel, dict) and channel is not None and "support" in channel else None
    resistance = channel["resistance"] if isinstance(channel, dict) and channel is not None and "resistance" in channel else None
    structure = "sideway_channel" if support is not None and resistance is not None else "no_channel"
    print(f"Source: MT5 historical data")
    print(f"Range: {start_date} to {end_date}")
    print(f"Trend: {'sideway' if support is not None and resistance is not None else 'no_channel'} ({structure})")

    if support is not None:
        ax.axhline(support["center"], color="red", linewidth=1.5, label=f"Support ({support['support_touches']} touches)")
    if resistance is not None:
        ax.axhline(resistance["center"], color="red", linewidth=1.5, label=f"Resistance ({resistance['resistance_touches']} touches)")

    if isinstance(channel, dict) and channel is not None and "structure" in channel and "x" in channel:
        channel_x = mdates.date2num(channel["x"])
        ax.plot(channel_x, channel["upper"], color="white", linewidth=1.2, label="H1 channel")
        ax.plot(channel_x, channel["lower"], color="white", linewidth=1.2)
        if "touches" in channel and len(channel["touches"]) >= 4:
            fourth_index, fourth_side, _ = channel["touches"][3]
            fourth_price = df.loc[fourth_index, "high"] if fourth_side == "resistance" else df.loc[fourth_index, "low"]
            ax.scatter(
                channel["confirmation_time"],
                fourth_price,
                color="yellow",
                s=60,
                zorder=5,
                label="4th H1 touch: channel confirmed",
            )
            print(f"Channel confirmed on H1 candle: {channel['confirmation_time']}")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    fig.autofmt_xdate()
    ax.set_title(f"{symbol.upper()} {timeframe.upper()} MT5 historical chart | {structure}", color="white")
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
    parser = argparse.ArgumentParser(description="Plot historical MT5 data without saving CSV files")
    parser.add_argument("--symbol", default="GOLD", help="MT5 symbol, for example GOLD or XAUUSD")
    parser.add_argument("--timeframe", default="h1", choices=sorted(TIMEFRAME_MAP), help="MT5 timeframe")
    parser.add_argument("--start-date", required=True, type=parse_date, help="First date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, type=parse_date, help="Last date, YYYY-MM-DD (inclusive)")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.end_date < args.start_date:
        raise ValueError("--end-date must be on or after --start-date")

    connect_to_mt5()
    try:
        df = load_mt5_data(args.symbol, args.timeframe, args.start_date, args.end_date)
        plot_candles(df, args.symbol, args.timeframe, args.start_date, args.end_date)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
