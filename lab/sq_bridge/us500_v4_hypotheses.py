"""Frozen identity contract for directed US500 D1 v4 hypotheses."""

FAMILIES = (
    "d1_time_series_momentum", "d1_shock_reversion",
    "d1_volatility_regime_trend",
)
MARKET_SIDES = ("both", "long", "short")

US500_PROFILE_BLOCKS = {
    "us500_d1_time_series_momentum_v4": {
        "Prices.Close", "Indicators.SMA", "Indicators.EMA", "Indicators.ROC",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "IsRising", "IsFalling", "BarDayOfWeekIs", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss",
    },
    "us500_d1_shock_reversion_v4": {
        "Prices.Close", "Indicators.ROC", "IsGreater", "IsLower",
        "CrossesAbove", "CrossesBelow", "IsRising", "IsFalling",
        "BarDayOfWeekIs", "EnterAtMarket", "ExitAfterBars.ExitAfterBars",
        "StopLoss.StopLoss",
    },
    "us500_d1_volatility_regime_trend_v4": {
        "Prices.Close", "Indicators.SMA", "Indicators.EMA", "Indicators.ROC",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "IsRising", "IsFalling", "BarDayOfWeekIs", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss",
    },
}

SEARCH_PROFILES = {
    f"{family}_{side}": f"us500_{family}_v4"
    for family in FAMILIES for side in MARKET_SIDES
}
HYPOTHESIS_MARKET_SIDES = {
    f"{family}_{side}": side
    for family in FAMILIES for side in MARKET_SIDES
}
