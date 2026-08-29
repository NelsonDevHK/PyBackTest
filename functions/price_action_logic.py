import numpy as np
import pandas as pd


def get_channel(df: pd.DataFrame, zone_threshold: float = 5.0, reaction_candles: int = 10, min_touches: int = 3):
    """Find hourly support/resistance zones that produce a move away and a later retest."""
    if df.empty:
        return {"support": None, "resistance": None}

    hourly_df = OneHour_df(df)
    if hourly_df.empty:
        return {"support": None, "resistance": None}

    prices = hourly_df["close"].astype(float).reset_index(drop=True)
    highs = hourly_df["high"].astype(float).reset_index(drop=True)
    lows = hourly_df["low"].astype(float).reset_index(drop=True)
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
                later = prices.iloc[departure_index + 1:]
                if ((later >= zone["center"] - zone_threshold) & (later <= zone["center"] + zone_threshold)).any():
                    zone["support_retests"] += 1
            elif moved_down and not moved_up:
                zone["resistance_touches"] += 1
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

    return {
        "support": support,
        "resistance": resistance,
    }


def OneHour_df(df: pd.DataFrame, title: str = ""):
    return (
        df.copy()
        .set_index("datetime")
        .resample("1h")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
        .reset_index()
    )

