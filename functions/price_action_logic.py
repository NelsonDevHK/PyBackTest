import numpy as np
import pandas as pd


def get_channel(
    df: pd.DataFrame,
    zone_threshold: float = 5.0,
    reaction_candles: int = 10,
    min_touches: int = 3,
):
    """Find a Mon-Wed M5 body channel, then fall back to horizontal support and resistance."""
    if df.empty:
        return _no_channel()

    analysis_df = df.sort_values("datetime").reset_index(drop=True)
    if analysis_df.empty:
        return _no_channel()

    # Establish the weekly setup before Thursday/Friday trading begins.
    setup_df = analysis_df[analysis_df["datetime"].dt.dayofweek <= 2].reset_index(drop=True)
    if setup_df.empty:
        return _no_channel()

    slope_channel = _find_slope_channel(setup_df, analysis_df)
    if slope_channel is not None:
        return slope_channel

    return _find_sideways_channel(setup_df, analysis_df, zone_threshold, reaction_candles, min_touches)


def _find_slope_channel(setup_df: pd.DataFrame, draw_df: pd.DataFrame):
    """Build parallel channel boundaries from M5 candle-body swing points."""
    body_tops = setup_df[["open", "close"]].max(axis=1).astype(float).reset_index(drop=True)
    body_bottoms = setup_df[["open", "close"]].min(axis=1).astype(float).reset_index(drop=True)
    candle_indices = np.arange(len(setup_df), dtype=float)
    price_range = float(body_tops.max() - body_bottoms.min())
    if len(setup_df) < 144 or price_range <= 0:
        return None

    pivot_highs = _pivot_indices(body_tops, find_high=True, window=12)
    pivot_lows = _pivot_indices(body_bottoms, find_high=False, window=12)
    if len(pivot_highs) < 2 or len(pivot_lows) < 2:
        return None

    touch_tolerance = max(price_range * 0.025, 0.01)
    minimum_slope = price_range / len(setup_df) * 0.03
    candidates = []

    for structure, anchors in (
        ("descending_channel", pivot_highs),
        ("ascending_channel", pivot_lows),
    ):
        for first_index, second_index in zip(anchors[:-1], anchors[1:]):
            slope = (body_tops.iloc[second_index] - body_tops.iloc[first_index]) / (second_index - first_index)
            if structure == "ascending_channel":
                slope = (body_bottoms.iloc[second_index] - body_bottoms.iloc[first_index]) / (second_index - first_index)

            if structure == "descending_channel" and slope >= -minimum_slope:
                continue
            if structure == "ascending_channel" and slope <= minimum_slope:
                continue

            upper_intercept = float(np.max(body_tops.to_numpy() - slope * candle_indices))
            lower_intercept = float(np.min(body_bottoms.to_numpy() - slope * candle_indices))
            channel_width = upper_intercept - lower_intercept
            if channel_width <= touch_tolerance * 2:
                continue

            touches = _line_touches(
                setup_df,
                pivot_highs,
                pivot_lows,
                slope,
                upper_intercept,
                lower_intercept,
                touch_tolerance,
            )
            upper_touches = sum(side == "resistance" for _, side, _ in touches)
            lower_touches = sum(side == "support" for _, side, _ in touches)
            if upper_touches < 2 or lower_touches < 2:
                continue

            candidates.append((len(touches), -channel_width, slope, structure, upper_intercept, lower_intercept, touches))

    if not candidates:
        return None

    _, _, slope, structure, upper_intercept, lower_intercept, touches = max(candidates)
    confirmation_time = _channel_confirmation_time(touches)
    if confirmation_time is None:
        return None
    draw_indices = np.arange(len(draw_df), dtype=float)
    upper = slope * draw_indices + upper_intercept
    lower = slope * draw_indices + lower_intercept
    return {
        "support": None,
        "resistance": None,
        "structure": structure,
        "slope": slope,
        "x": draw_df["datetime"],
        "upper": upper,
        "lower": lower,
        "touches": touches,
        "confirmation_time": confirmation_time,
    }


def _pivot_indices(prices: pd.Series, find_high: bool, window: int = 2) -> list[int]:
    pivots = []
    for index in range(window, len(prices) - window):
        nearby = prices.iloc[index - window:index + window + 1]
        price = prices.iloc[index]
        if (find_high and price == nearby.max()) or (not find_high and price == nearby.min()):
            pivots.append(index)
    return pivots


def _line_touches(
    setup_df: pd.DataFrame,
    pivot_highs: list[int],
    pivot_lows: list[int],
    slope: float,
    upper_intercept: float,
    lower_intercept: float,
    tolerance: float,
) -> list[tuple[pd.Timestamp, str, float]]:
    touches = []
    body_tops = setup_df[["open", "close"]].max(axis=1)
    body_bottoms = setup_df[["open", "close"]].min(axis=1)
    for index in pivot_highs:
        line_price = slope * index + upper_intercept
        price = float(body_tops.iloc[index])
        if abs(price - line_price) <= tolerance:
            touches.append((setup_df.loc[index, "datetime"], "resistance", price))
    for index in pivot_lows:
        line_price = slope * index + lower_intercept
        price = float(body_bottoms.iloc[index])
        if abs(price - line_price) <= tolerance:
            touches.append((setup_df.loc[index, "datetime"], "support", price))
    touches = sorted(touches, key=lambda touch: touch[0])
    return [touch for index, touch in enumerate(touches) if index == 0 or (touch[0] - touches[index - 1][0]) >= pd.Timedelta(minutes=60)]


def _find_sideways_channel(
    setup_df: pd.DataFrame,
    draw_df: pd.DataFrame,
    zone_threshold: float,
    reaction_candles: int,
    min_touches: int,
):
    """Find hourly support/resistance zones that produce a move away and a later retest."""

    prices = setup_df["close"].astype(float).reset_index(drop=True)
    highs = setup_df[["open", "close"]].max(axis=1).astype(float).reset_index(drop=True)
    lows = setup_df[["open", "close"]].min(axis=1).astype(float).reset_index(drop=True)
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
            "support_events": [],
            "resistance_events": [],
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
                zone["support_events"].append((setup_df.loc[index, "datetime"], "support", zone["center"]))
                departure_index = index + 1 + int((future >= zone["center"] + zone_threshold).to_numpy().argmax())
                later = prices.iloc[departure_index + 1:]
                if ((later >= zone["center"] - zone_threshold) & (later <= zone["center"] + zone_threshold)).any():
                    zone["support_retests"] += 1
            elif moved_down and not moved_up:
                zone["resistance_touches"] += 1
                zone["resistance_events"].append((setup_df.loc[index, "datetime"], "resistance", zone["center"]))
                departure_index = index + 1 + int((future <= zone["center"] - zone_threshold).to_numpy().argmax())
                later = prices.iloc[departure_index + 1:]
                if ((later >= zone["center"] - zone_threshold) & (later <= zone["center"] + zone_threshold)).any():
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

    touches = []
    if support is not None:
        touches.extend(support["support_events"])
    if resistance is not None:
        touches.extend(resistance["resistance_events"])
    touches.sort(key=lambda touch: touch[0])
    confirmation_time = _channel_confirmation_time(touches)
    is_confirmed = (
        support is not None
        and resistance is not None
        and confirmation_time is not None
    )

    return {
        "support": support,
        "resistance": resistance,
        "structure": "sideway_channel" if is_confirmed else "no_channel",
        "x": draw_df["datetime"] if is_confirmed else None,
        "upper": np.full(len(draw_df), resistance["center"]) if is_confirmed else None,
        "lower": np.full(len(draw_df), support["center"]) if is_confirmed else None,
        "touches": touches if is_confirmed else [],
        "confirmation_time": confirmation_time if is_confirmed else None,
    }


def _channel_confirmation_time(touches: list[tuple[pd.Timestamp, str, float]]) -> pd.Timestamp | None:
    """Confirm only after two accepted touches are present on both channel boundaries."""
    support_touches = 0
    resistance_touches = 0
    for timestamp, side, _ in touches:
        if side == "support":
            support_touches += 1
        else:
            resistance_touches += 1
        if support_touches >= 2 and resistance_touches >= 2:
            return timestamp
    return None


def _no_channel():
    return {"support": None, "resistance": None, "structure": "no_channel"}


def OneHour_df(df: pd.DataFrame, title: str = ""):
    return (
        df.copy()
        .set_index("datetime")
        .resample("1h")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
        .reset_index()
    )

