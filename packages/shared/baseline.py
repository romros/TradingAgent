"""
Baseline MSFT D1 (capitulation_d1) — referència del backtest.
Ús: comparació paper vs backtest per validació T7b.
"""

# MSFT D1: WR 78%, EV +12.7$/trade (T6d/T6e)
BASELINE_MSFT_D1 = {
    "winrate_pct": 78.0,
    "avg_pnl_per_trade": 12.7,
}

# Marges per classificació (heurística simple)
MARGIN_WR_PCT = 10.0   # ±10%
MARGIN_EV_PCT = 30.0   # ±30% (sobre baseline EV)

# probe_ok: últim scan vàlid si < 48h
PROBE_OK_MAX_AGE_HOURS = 48
