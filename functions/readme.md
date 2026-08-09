# PyBackTest

PyBackTest is a strategy testing project focused on evaluating and improving trading performance before going live.

## Project Goal

The main goal of this project is to:

- Test the overall strategy in a structured way.
- Tune parameters to improve win rate and stability.
- Move the best-performing version into live execution.

## Current Stage

Phase 1 focuses on **Price Action testing**.

This includes:

- Defining clear entry and exit rules from price behavior.
- Backtesting on historical candles.
- Measuring win rate, drawdown, and consistency.

More strategy modules will be added in the next phases.

## Project Status

- In progress
- First milestone: Price Action backtest baseline
- To be continued with additional strategies

## Quick Start

1. Make sure Python is installed.
2. Run:

```bash
python main.py
```

Current `main.py` is a starter file and will be expanded with backtesting logic.

## Data Requirement (Priority)

Preferred market data for this project:

1. XAUUSD 15-minute candles
2. XAUUSD 1-hour candles
3. If unavailable, use another reliable gold-related dataset as fallback

Minimum candle fields:

- Timestamp (UTC preferred)
- Open
- High
- Low
- Close
- Volume (optional but useful)

## Recommended Data Sources

### Priority A: XAUUSD (15m / 1h)

1. Dukascopy Historical Data Export
	- Link: https://www.dukascopy.com/swiss/english/marketwatch/historical/
	- Notes: Reliable historical market source. You can export and then resample/use 15m and 1h candles.

2. Kaggle XAUUSD datasets (community maintained)
	- Link: https://www.kaggle.com/search?q=XAUUSD
	- Notes: Good for quick start. Verify timeframe columns and data quality before use.

### Priority B: API-based alternatives

3. Alpha Vantage FX intraday / gold endpoints
	- Docs: https://www.alphavantage.co/documentation/
	- Notes: Supports 15min and 60min intervals for FX APIs. Check symbol support and plan limits.

## Suggested First Dataset Workflow

1. Try Dukascopy export for XAUUSD first.
2. Validate candle continuity and timezone.
3. If you need a faster start, use a Kaggle XAUUSD dataset that already has 15m or 1h candles.
4. Standardize all files into one schema before backtesting.

## Next Development Steps

1. Build data loader and cleaner.
2. Implement backtest engine (entry, exit, SL/TP, fees/spread).
3. Add performance report (win rate, RR, drawdown, expectancy).
4. Add parameter tuning loop.
5. Prepare paper/live deployment module.

## Notes for Collaboration

- Keep strategy logic isolated from data loading.
- Save test results per run for reproducibility.
- Version-control strategy parameter sets.

