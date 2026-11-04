"""Run the channel strategy over one MT5 data window per week."""

import argparse
from datetime import date, timedelta

import MetaTrader5 as mt5

from fetch_mt5 import TIMEFRAME_MAP, connect_to_mt5
from price_action_historical import load_mt5_data, simulate_trade
from price_action_logic import get_channel


def monday_weeks(start_date: date, end_date: date):
	current = start_date - timedelta(days=start_date.weekday())
	while current <= end_date:
		week_end = current + timedelta(days=4)
		if week_end >= start_date and current <= end_date:
			yield max(current, start_date), min(week_end, end_date)
		current += timedelta(days=7)


def run_backtest(symbol: str, timeframe: str, start_date: date, end_date: date) -> dict:
	report = {
		"weeks_checked": 0,
		"channel_catches": 0,
		"week_skips": 0,
		"wins": 0,
		"losses": 0,
		"open_trades": 0,
		"weeks": [],
	}

	for week_start, week_end in monday_weeks(start_date, end_date):
		report["weeks_checked"] += 1
		week = {"start": week_start, "end": week_end}
		try:
			df = load_mt5_data(symbol, timeframe, week_start, week_end)
		except RuntimeError as exc:
			report["week_skips"] += 1
			week["status"] = "skip"
			week["reason"] = str(exc)
			report["weeks"].append(week)
			continue

		channel = get_channel(df)
		has_channel = channel.get("structure") != "no_channel" and channel.get("confirmation_time") is not None
		trade = simulate_trade(df, channel) if has_channel else None
		if not has_channel:
			report["week_skips"] += 1
			week["status"] = "skip"
			week["reason"] = "no confirmed channel"
		else:
			report["channel_catches"] += 1
			week["status"] = trade["result"]
			week["trade"] = trade
			result_key = {"win": "wins", "loss": "losses", "open": "open_trades"}.get(trade["result"])
			if result_key == "open_trades":
				report["open_trades"] += 1
			elif result_key is not None:
				report[result_key] += 1
		report["weeks"].append(week)

	return report


def parse_args():
	parser = argparse.ArgumentParser(description="Backtest the channel strategy week by week")
	parser.add_argument("--symbol", default="GOLD")
	parser.add_argument("--timeframe", default="m5", choices=sorted(TIMEFRAME_MAP))
	parser.add_argument("--start-date", type=date.fromisoformat, default=date(2025, 1, 6))
	parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
	return parser.parse_args()


def main():
	args = parse_args()
	if args.end_date < args.start_date:
		raise ValueError("--end-date must be on or after --start-date")

	connect_to_mt5()
	try:
		report = run_backtest(args.symbol, args.timeframe, args.start_date, args.end_date)
	finally:
		mt5.shutdown()

	print(f"Weeks checked: {report['weeks_checked']}")
	print(f"Channel catches: {report['channel_catches']}")
	print(f"Week skips: {report['week_skips']}")
	print(f"Wins: {report['wins']}")
	print(f"Losses: {report['losses']}")
	print(f"Open at week end: {report['open_trades']}")


if __name__ == "__main__":
	main()
