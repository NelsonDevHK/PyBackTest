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


def simulate_trade(
    df: pd.DataFrame,
    channel: dict,
    reward_risk: float = 2.5,
) -> dict | None:
    """Enter on the channel-confirming candle and resolve the trade forward."""
    confirmation_time = channel.get("confirmation_time")
    touches = channel.get("touches", [])
    if confirmation_time is None or not touches or reward_risk <= 0:
        return None

    entry_index = df.index[df["datetime"] == confirmation_time]
    if len(entry_index) == 0:
        return None

    entry_index = int(entry_index[0])
    channel_index = df.index[df["datetime"] == confirmation_time]
    projected_index = int(channel_index[0])
    upper = float(channel["upper"][projected_index])
    lower = float(channel["lower"][projected_index])
    confirmation_touch = next(
        (touch for touch in touches if touch[0] == confirmation_time),
        None,
    )
    if confirmation_touch is None:
        return None
    side = confirmation_touch[1]
    direction = "short" if side == "resistance" else "long"
    entry = float(df.loc[entry_index, "close"])
    target = lower if direction == "short" else upper
    risk = abs(target - entry) / reward_risk
    stop = entry + risk if direction == "short" else entry - risk

    for index in range(entry_index, len(df)):
        candle = df.iloc[index]
        hit_target = candle["low"] <= target if direction == "long" else candle["high"] >= target
        hit_stop = candle["low"] <= stop if direction == "long" else candle["high"] >= stop
        if hit_target and hit_stop:
            result = "loss"
            exit_price = stop
            exit_reason = "stop_and_target_same_candle_stop_first"
        elif hit_target:
            result = "win"
            exit_price = target
            exit_reason = "target"
        elif hit_stop:
            result = "loss"
            exit_price = stop
            exit_reason = "stop"
        else:
            continue
        return {
            "entry_time": confirmation_time,
            "entry": entry,
            "direction": direction,
            "target": target,
            "stop": stop,
            "exit_time": candle["datetime"],
            "exit": exit_price,
            "result": result,
            "exit_reason": exit_reason,
        }

    return {
        "entry_time": confirmation_time,
        "entry": entry,
        "direction": direction,
        "target": target,
        "stop": stop,
        "exit_time": None,
        "exit": None,
        "result": "open",
        "exit_reason": "week_ended",
    }


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
    structure = channel.get("structure", "no_channel") if isinstance(channel, dict) else "no_channel"
    print(f"Source: MT5 historical data")
    print(f"Range: {start_date} to {end_date}")
    print(f"Trend: {structure}")
    if "slope" in channel:
        print(f"M5 slope: {channel['slope']:.4f} price units per candle")

    is_confirmed_channel = structure != "no_channel" and "x" in channel and channel["x"] is not None
    if support is not None and not is_confirmed_channel:
        ax.axhline(support["center"], color="red", linewidth=1.5, label=f"Support ({support['support_touches']} touches)")
    if resistance is not None and not is_confirmed_channel:
        ax.axhline(resistance["center"], color="red", linewidth=1.5, label=f"Resistance ({resistance['resistance_touches']} touches)")

    if is_confirmed_channel:
        channel_x = mdates.date2num(channel["x"])
        channel_label = "sideway channel" if structure == "sideway_channel" else f"{structure} (M5 body)"
        ax.plot(channel_x, channel["upper"], color="white", linewidth=1.2, label=channel_label)
        ax.plot(channel_x, channel["lower"], color="white", linewidth=1.2)
        if "touches" in channel and len(channel["touches"]) >= 4:
            entry_candles = df[df["datetime"] > channel["confirmation_time"]]
            if not entry_candles.empty:
                entry_candle = entry_candles.iloc[0]
                ax.scatter(
                    entry_candle["datetime"],
                    entry_candle["close"],
                    color="yellow",
                    s=60,
                    zorder=5,
                    label="First candle after channel confirmation",
                )
                print(f"Channel confirmed: {channel['confirmation_time']}")
                print(f"First eligible entry candle: {entry_candle['datetime']}")

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
