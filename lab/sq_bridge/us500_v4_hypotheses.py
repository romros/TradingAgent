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


def accepted_target(hypothesis_id: str, selected_ids: list[str],
                    global_budget: int = 60) -> int:
    """Split the frozen global candidate budget across valid US500 branches."""
    if (not isinstance(global_budget, int) or isinstance(global_budget, bool)
            or global_budget < 1):
        raise ValueError("global candidate budget must be positive")
    selected = sorted(selected_ids)
    if (not selected or selected != sorted(set(selected))
            or any(value not in SEARCH_PROFILES for value in selected)
            or hypothesis_id not in selected):
        raise ValueError("selected directed hypotheses are invalid")
    quotient, remainder = divmod(global_budget, len(selected))
    target = quotient + (1 if selected.index(hypothesis_id) < remainder else 0)
    if target < 1:
        raise ValueError("more branches than the global candidate budget")
    return target
