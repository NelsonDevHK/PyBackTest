import argparse
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from path_utils import get_data_dir, load_project_env

load_project_env()

TIMEFRAME_MAP = {
    "m1": mt5.TIMEFRAME_M1,
    "m5": mt5.TIMEFRAME_M5,
    "m15": mt5.TIMEFRAME_M15,
    "m30": mt5.TIMEFRAME_M30,
    "h1": mt5.TIMEFRAME_H1,
    "h4": mt5.TIMEFRAME_H4,
    "d1": mt5.TIMEFRAME_D1,
    "w1": mt5.TIMEFRAME_W1,
    "mn1": mt5.TIMEFRAME_MN1,
}


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(" ", "")


def file_name_for_day(symbol: str, date_value: str, timeframe_name: str) -> str:
    dt = datetime.fromisoformat(date_value)
    weekday = dt.strftime("%a").lower()
    clean_symbol = normalize_symbol(symbol).lower().replace("/", "_").replace(".", "_")
    tf_key = timeframe_name.lower()
    return f"{clean_symbol}_{tf_key}_{date_value}_{weekday}.csv" 


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def connect_to_mt5() -> None:
    login_value = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    terminal_path = os.getenv("MT5_PATH")

    missing = [
        name
        for name, value in (
            ("MT5_LOGIN", login_value),
            ("MT5_PASSWORD", password),
            ("MT5_SERVER", server),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing MT5 settings in .env: " + ", ".join(missing))

    initialize_args = {}
    if terminal_path:
        terminal_path = terminal_path.strip().strip('"')
        if Path(terminal_path).is_file():
            initialize_args["path"] = terminal_path
        else:
            print(f"Warning: MT5_PATH does not exist, using the default terminal: {terminal_path}")

    if not mt5.initialize(**initialize_args):
        raise RuntimeError(f"MT5 connection failed: {mt5.last_error()}")

    account_info = mt5.account_info()
    if account_info is None:
        if not mt5.login(int(login_value), password=password, server=server):
            error = mt5.last_error()
            mt5.shutdown()
            raise RuntimeError(f"MT5 login failed: {error}")
        account_info = mt5.account_info()

    if account_info is None:
        error = mt5.last_error()
        mt5.shutdown()
        raise RuntimeError(f"MT5 connected but account information was unavailable: {error}")

    if str(account_info.login) != login_value or account_info.server != server:
        if not mt5.login(int(login_value), password=password, server=server):
            error = mt5.last_error()
            mt5.shutdown()
            raise RuntimeError(f"MT5 account switch failed: {error}")
        account_info = mt5.account_info()

    print(f"Connected to MT5 account {account_info.login} on {account_info.server}")


def fetch_day_mt5(symbol: str, timeframe_name: str, day: date, output_dir: Path) -> Path:
    tf_key = timeframe_name.lower()
    if tf_key not in TIMEFRAME_MAP:
        raise ValueError(f"Unsupported timeframe: {timeframe_name}. Use one of {sorted(TIMEFRAME_MAP)}")

    start_dt = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)

    symbol_name = normalize_symbol(symbol)
    if not mt5.symbol_select(symbol_name, True):
        raise RuntimeError(f"MT5 could not select symbol '{symbol_name}': {mt5.last_error()}")

    rates = mt5.copy_rates_range(
        symbol_name,
        TIMEFRAME_MAP[tf_key],
        start_dt,
        end_dt,
    )

    if rates is None or len(rates) == 0:
        raise RuntimeError(
            f"No MT5 data returned for {symbol_name} on {day.isoformat()} ({timeframe_name})"
        )

    df = pd.DataFrame(rates)
    if "time" not in df.columns:
        raise RuntimeError("MT5 response did not contain a 'time' column")

    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    start_naive = start_dt.replace(tzinfo=None)
    end_naive = end_dt.replace(tzinfo=None)
    df = df[(df["datetime"] >= start_naive) & (df["datetime"] < end_naive)]
    columns = ["datetime", "open", "high", "low", "close"]
    optional_columns = ["tick_volume", "spread", "real_volume"]
    df = df[[column for column in columns + optional_columns if column in df.columns]]
    df = df.sort_values("datetime", ascending=True).reset_index(drop=True)

    day_text = day.isoformat()
    output_path = output_dir / file_name_for_day(symbol, day_text, timeframe_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} bars: {output_path}")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch an inclusive date range of CFD bars from MT5 and save daily CSV files"
    )
    parser.add_argument("--symbol", default="GOLD", help="MT5 symbol name, for example XAUUSD or XAUUSDm")
    parser.add_argument("--timeframe", default="m5", choices=sorted(TIMEFRAME_MAP), help="MT5 timeframe to fetch")
    parser.add_argument("--start-date", required=True, type=parse_date, help="First date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, type=parse_date, help="Last date, YYYY-MM-DD (inclusive)")
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = get_data_dir()

    if args.end_date < args.start_date:
        raise ValueError("--end-date must be on or after --start-date")

    connect_to_mt5()
    try:
        current_day = args.start_date
        while current_day <= args.end_date:
            fetch_day_mt5(args.symbol, args.timeframe, current_day, output_dir)
            current_day += timedelta(days=1)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()