# price_action_backtest.py

This file currently loads historical GOLD candles, converts them to hourly candles for analysis, finds support and resistance zones, and displays the result on a candlestick chart.

It does not place trades and it does not connect to MT5. The data must already exist in `5MinutesData`.

## Run The File

From the `functions` folder:

```powershell
python price_action_backtest.py --symbol GOLD --timeframe m5 --start-date 2026-08-10 --end-date 2026-08-14
```

If the virtual environment is not activated, use:

```powershell
..\.venv\Scripts\python.exe price_action_backtest.py --symbol GOLD --timeframe m5 --start-date 2026-08-10 --end-date 2026-08-14
```

The end date is included.

## Expected CSV Columns

Required columns:

```text
datetime, open, high, low, close
```

Optional MT5 columns:

```text
tick_volume, spread, real_volume
```

## Function Flow

```text
parse_args()
	-> load_data()
	-> plot_candles()
		-> get_support_resistance()
			-> OneHour_df()
```

## `load_data()`

```python
load_data(symbol, timeframe, start_date, end_date)
```

Loads matching daily CSV files from `5MinutesData`, keeps files inside the requested date range, converts `datetime`, combines the files, and sorts them chronologically.

Example:

```python
df = load_data("GOLD", "m5", "2026-08-10", "2026-08-14")
```

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

## `get_support_resistance()`

```python
get_support_resistance(
	df,
	zone_threshold=5.0,
	reaction_candles=10,
	min_touches=3,
)
```

Finds price zones that cause a meaningful move away and are later retested. It analyzes the H1 candles created by `OneHour_df()`.

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

Displays the original requested timeframe as candlesticks and draws the selected levels.

- Candles remain M5 when `--timeframe m5` is used.
- Analysis uses H1 candles.
- Support and resistance lines are both blue.
- The legend shows directional touch counts.
- No PNG file is saved.

## `parse_args()`

Defines the command-line options:

```text
--symbol       default: GOLD
--timeframe    default: m5
--start-date   default: 2026-07-27
--end-date     default: 2026-07-31
```

The values are passed to `load_data()` by `main()`.

## `main()`

Runs the workflow:

1. Read command-line arguments.
2. Load the selected CSV data.
3. Draw the candlestick chart.
4. Calculate hourly support and resistance.
5. Display the chart.

## Current Limitations

- Trend detection is not implemented yet.
- Fibonacci levels are not implemented yet.
- Entry, TP, and SL rules are not implemented yet.
- Historical trade simulation is not implemented yet.
- The levels are based on candle prices, not order-book data.
- A short date range may not contain enough hourly candles for reliable retests.

## Next Development Steps

1. Add trend classification.
2. Add Fibonacci levels at `0`, `0.618`, `0.88`, `1`, and `-0.272`.
3. Define entry, TP, and SL rules.
4. Simulate historical trades candle by candle.
5. Add win rate, net result, drawdown, and average R reporting.