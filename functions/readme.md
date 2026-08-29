# Price Action Channel Analysis

The active workflow is centered on a single shared channel detector:

- `price_action_historical.py`: reads historical candles directly from MT5 without saving CSV files and plots the detected support/resistance channel.
- `price_action_logic.py`: contains the reusable channel logic, including `get_channel()` and `OneHour_df()`.
- `all_pattern.py`: older compatibility/testing script; it is not the primary historical workflow anymore.

## Local CSV Review

Use this when the data already exists in `5MinutesData`:

```powershell
python price_action_local.py --symbol GOLD --timeframe m5 --start-date 2026-08-10 --end-date 2026-08-14
```

If the virtual environment is not activated, use:

```powershell
..\.venv\Scripts\python.exe price_action_local.py --symbol GOLD --timeframe m5 --start-date 2026-08-10 --end-date 2026-08-14
```

## Direct MT5 Historical Review

Use this when you want MT5 to provide the historical candles directly:

```powershell
python price_action_historical.py --symbol GOLD --timeframe h1 --start-date 2026-08-03 --end-date 2026-08-07
```

This script:

1. Connects to the configured MT5 account.
2. Requests the exact date range from MT5.
3. Plots the returned candles.
4. Runs the channel analysis.
5. Does not save the returned data as CSV.

The date range is controlled entirely by the command. It is not fixed to one week. The end date is included.

## Main Historical Workflow

Use the direct MT5 chart script for the active workflow:

```powershell
python price_action_historical.py --symbol GOLD --timeframe m5 --start-date 2026-08-10 --end-date 2026-08-14
```

This script:

1. Connects to the configured MT5 account.
2. Loads the requested date range directly from MT5.
3. Draws the candlestick chart.
4. Runs the current channel detector via `get_channel()`.
5. Draws the detected support/resistance lines in red.
6. Does not save the returned data as CSV.

The date range is controlled entirely by the command. It is not fixed to one week, and the end date is included.

> The older four-touch all-pattern scanner is kept mainly as a deferred/legacy experiment. The primary and working path is the historical channel workflow.

## Expected CSV Columns

Required columns:

```text
datetime, open, high, low, close
```

Optional MT5 columns:

```text
tick_volume, spread, real_volume
```

## Shared Function Flow

```text
parse_args()
	-> load_data() or load_mt5_data()
	-> plot_candles()
		-> get_channel()
			-> OneHour_df()
```

## Local `load_data()`

```python
load_data(symbol, timeframe, start_date, end_date)
```

Loads matching daily CSV files from `5MinutesData`, keeps files inside the requested date range, converts `datetime`, combines the files, and sorts them chronologically.

Example:

```python
df = load_data("GOLD", "m5", "2026-08-10", "2026-08-14")
```

## `load_mt5_data()`

```python
load_mt5_data(symbol, timeframe, start_date, end_date)
```

Requests historical bars directly from MT5 using `copy_rates_range()`.

It converts MT5 timestamps into the project `datetime` column, keeps only the requested range, sorts the rows, and returns a DataFrame in memory.

No downloaded CSV is created.

## `OneHour_df()`

```python
OneHour_df(df, title="")
```

Converts the loaded candles into one-hour OHLC candles:

```python
df.resample("1h").agg({
	"open": "first",
	"high": "max",
	"low": "min",
	"close": "last",
})
```

The `title` argument is currently retained for compatibility but is not used in the calculation.

The chart can remain M5 while support and resistance are calculated from H1 data.

## `get_channel()`

```python
get_channel(
	df,
	zone_threshold=5.0,
	reaction_candles=10,
	min_touches=3,
)
```

Finds the best support and resistance zone candidate for the selected historical window. It analyzes H1 candles created by `OneHour_df()`. The result contains the strongest support level and the strongest resistance level, each with its touch and retest counters.

This is the active function name in the current codebase. Older scripts may still mention `get_support_resistance()`, but the main logic now lives in `get_channel()` directly.

### Parameters

- `zone_threshold=5.0`: approximately ±5 price units around a zone center.
- `reaction_candles=10`: number of later hourly candles checked for a reaction.
- `min_touches=3`: minimum number of directional reactions required for selection.

Zone centers are spaced by 10 points so neighboring ±5 zones do not overlap.

Example:

```text
Center: 4320
Zone:   4315 to 4325
```

### Touch logic

Only the first hourly candle entering a zone from outside counts as a touch. Candles that remain inside the zone do not create extra touches.

### Reaction logic

For each touch, the next 10 hourly closes are checked:

- Move above the zone: support reaction.
- Move below the zone: resistance reaction.
- Both directions: ambiguous touch, ignored.

### Retest logic

After the price leaves the zone, later hourly closes are checked. A return inside the zone counts as a retest.

Retests are ranked more strongly than raw touches because they show that the level was respected, left, and tested again.

### Candidate selection

- Support candidates must be in the lower quarter of the hourly range.
- Resistance candidates must be in the upper quarter.
- Retest count is ranked first.
- Directional touch count breaks ties.

The result has this structure:

```python
{
	"support": {
		"center": 4320,
		"support_touches": 3,
		"support_retests": 2,
	},
	"resistance": {
		"center": 4430,
		"resistance_touches": 3,
		"resistance_retests": 2,
	},
}
```

If no qualifying zone exists, the value is `None`.

## `plot_candles()`

```python
plot_candles(df, title)
```

Displays candles and draws the detected channel.

- Local plotting uses the requested CSV timeframe.
- Direct historical plotting uses the requested MT5 timeframe.
- Channel analysis uses H1 candles.
- Support and resistance lines are both red.
- The legend shows touch counts for the selected support and resistance levels.
- No PNG file is saved.

## `parse_args()`

`price_action_logic.py` defines:

```text
--symbol       default: GOLD
--timeframe    default: m5
--start-date   default: 2026-07-27
--end-date     default: 2026-07-31
```

The values are passed to `load_data()` by `main()`.

`price_action_historical.py` defines the same date arguments, but uses `load_mt5_data()` instead.

## `main()`

Runs the workflow:

1. Read command-line arguments.
2. Load local CSV data or direct MT5 data.
3. Draw the candlestick chart.
4. Calculate the channel.
5. Display the chart.

## Current Limitations

- The current detector is a support/resistance zone finder, not a full trade engine.
- A valid channel is treated as a sideways zone by the current logic.
- Fibonacci levels are not implemented yet.
- Entry, TP, and SL rules are not implemented yet.
- Historical trade simulation is not implemented yet.
- The levels are based on candle prices, not order-book data.
- A short date range may not contain enough hourly candles for reliable retests.

## Next Development Steps

1. Add Fibonacci levels at `0`, `0.618`, `0.88`, `1`, and `-0.272`.
3. Define entry, TP, and SL rules.
4. Simulate historical trades candle by candle.
5. Add win rate, net result, drawdown, and average R reporting.