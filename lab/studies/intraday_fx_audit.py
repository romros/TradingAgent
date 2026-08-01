"""Deep audit of the strongest dev-only near-candidate from the FX campaign."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import intraday_fx_campaign as campaign


OUT = Path("/work/lab/out/intraday_fx_campaign")
FAMILY = "vol_expansion"
SYMBOL = "EURUSD"
PARAMS = (2, 12)
HOLD = 6
LEVERAGE = 10
COLLATERAL_PCT = .20


def pnl_series(trades: pd.DataFrame, cost_mult: float) -> pd.Series:
    cap = campaign.CAPITAL
    values = []
    dates = []
    for row in trades.itertuples():
        collateral = cap * COLLATERAL_PCT
        nominal = collateral * LEVERAGE
        if row.mae >= 1 / LEVERAGE:
            pnl = -collateral - campaign.GAS_RT * cost_mult
        else:
            variable = nominal * campaign.VARIABLE_COST[SYMBOL] * cost_mult
            borrowed = nominal * (1 - 1 / LEVERAGE)
            finance = borrowed * campaign.FINANCING * (row.bars * 4 / 24 / 365)
            pnl = nominal * row.move - variable - campaign.GAS_RT * cost_mult - finance
        values.append(pnl)
        dates.append(pd.Timestamp(row.entry))
        cap = max(cap + pnl, 0)
        if cap <= 0:
            break
    return pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float)


def main() -> None:
    data = campaign.load_4h(SYMBOL)
    trades = campaign.make_trades(data, campaign.signals(FAMILY, data, PARAMS), HOLD)
    assert (pd.to_datetime(trades.entry, utc=True) > pd.to_datetime(trades.signal, utc=True)).all()
    assert LEVERAGE <= 10 and campaign.CAPITAL * COLLATERAL_PCT <= 50

    report = {
        "configuration": {"family": FAMILY, "symbol": SYMBOL, "params": PARAMS,
                          "hold_4h_bars": HOLD, "leverage": LEVERAGE,
                          "collateral_pct": COLLATERAL_PCT, "capital_usd": campaign.CAPITAL},
        "splits": {},
    }
    rng = np.random.default_rng(20260801)
    for split_name in ("dev", "validation", "test"):
        subset = campaign.split(trades, split_name)
        item = {"n": len(subset), "cost_scenarios": {}, "directions": {}, "yearly": {}}
        for multiplier in (1, 2, 3):
            item["cost_scenarios"][str(multiplier)] = campaign.simulate(
                subset, SYMBOL, LEVERAGE, multiplier, COLLATERAL_PCT)
        for side, label in ((1, "long"), (-1, "short")):
            direction = subset[subset.side == side]
            item["directions"][label] = campaign.simulate(
                direction, SYMBOL, LEVERAGE, 1, COLLATERAL_PCT)
        pnl = pnl_series(subset, 1)
        if len(pnl):
            item["yearly"] = {str(k.year): float(v) for k, v in pnl.resample("YE").sum().items()}
            means = rng.choice(pnl.to_numpy(), size=(10_000, len(pnl)), replace=True).mean(axis=1)
            item["bootstrap_mean_pnl_95pct"] = [float(x) for x in np.quantile(means, [.025, .975])]
            item["mae_p99"] = float(subset.mae.quantile(.99))
            item["liquidation_distance"] = 1 / LEVERAGE
        report["splits"][split_name] = item

    (OUT / "near_candidate_audit.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
