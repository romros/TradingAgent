"""Frozen identity contract for directed EURUSD D1 v4 hypotheses."""

FAMILIES = ("d1_breakout", "d1_momentum", "d1_shock_reversion")
MARKET_SIDES = ("both", "long", "short")

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
