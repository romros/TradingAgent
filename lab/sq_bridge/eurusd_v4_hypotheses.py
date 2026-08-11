"""Frozen identity contract for directed EURUSD D1 v4 hypotheses."""

FAMILIES = ("d1_breakout", "d1_momentum", "d1_shock_reversion")
MARKET_SIDES = ("both", "long", "short")

EURUSD_PROFILE_BLOCKS = {
    "eurusd_d1_breakout_v4": {
        "Prices.Close", "Prices.High", "Prices.Low",
        "Indicators.Highest", "Indicators.Lowest",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "BarDayOfWeekIs", "EnterAtMarket", "ExitAfterBars.ExitAfterBars",
        "StopLoss.StopLoss",
    },
    "eurusd_d1_momentum_v4": {
        "Prices.Close", "Indicators.SMA", "Indicators.EMA", "Indicators.ROC",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "BarDayOfWeekIs", "IsRising", "IsFalling", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss",
    },
    "eurusd_d1_shock_reversion_v4": {
        "Prices.Close", "Indicators.RSI", "Indicators.ROC",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "BarDayOfWeekIs", "IsRising", "IsFalling", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss",
    },
}

SEARCH_PROFILES = {
    f"{family}_{side}": f"eurusd_{family}_v4"
    for family in FAMILIES
    for side in MARKET_SIDES
}

HYPOTHESIS_MARKET_SIDES = {
    f"{family}_{side}": side
    for family in FAMILIES
    for side in MARKET_SIDES
}


def accepted_target(hypothesis_id: str, selected_ids: list[str],
                    global_budget: int = 60) -> int:
    """Split a global candidate budget exactly across frozen screen branches."""
    if (not isinstance(global_budget, int) or isinstance(global_budget, bool)
            or global_budget < 1):
        raise ValueError("global candidate budget must be positive")
    selected = sorted(selected_ids)
    if (not selected or selected != sorted(set(selected))
            or any(value not in SEARCH_PROFILES for value in selected)
            or hypothesis_id not in selected):
        raise ValueError("selected directed hypotheses are invalid")
    quotient, remainder = divmod(global_budget, len(selected))
    index = selected.index(hypothesis_id)
    target = quotient + (1 if index < remainder else 0)
    if target < 1:
        raise ValueError("more branches than the global candidate budget")
    return target
