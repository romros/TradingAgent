#!/usr/bin/env python3
"""Train-only falsification screen for GBPUSD post-London-fix reversal v26."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.gbpusd_m15_v1 import load_m15


def daily_signals(frame: pd.DataFrame) -> pd.DataFrame:
    local = frame.copy()
    local.index = local.index.tz_convert("Europe/London")
    rows = []
    for date, day in local.groupby(local.index.date, sort=False):
        by_time = {(t.hour, t.minute): row for t, row in day.iterrows()}
        start, entry = by_time.get((15, 0)), by_time.get((16, 0))
        if start is None or entry is None:
            continue
        move = float(entry.o / start.o - 1)
        rows.append({"date": pd.Timestamp(date, tz="Europe/London"), "move": move,
                     "entry": float(entry.o), "day": day})
    signals = pd.DataFrame(rows)
    if signals.empty:
        return signals
    signals["baseline"] = signals.move.abs().shift(1).rolling(20, min_periods=20).median()
    return signals


def simulate(signals: pd.DataFrame, shock_multiple: float, stop_multiple: float, exit_hour: int) -> pd.DataFrame:
    trades = []
    for row in signals.itertuples():
        if not row.baseline or row.baseline <= 0 or abs(row.move) < shock_multiple * row.baseline:
            continue
        side = -1 if row.move > 0 else 1
        stop_distance = max(abs(row.move) * stop_multiple * row.entry, row.entry * 0.0005)
        stop = row.entry - side * stop_distance
        window = row.day[(row.day.index >= row.date + pd.Timedelta(hours=16))
                         & (row.day.index < row.date + pd.Timedelta(hours=exit_hour))]
        if window.empty:
            continue
        exit_price, exit_time = float(window.iloc[-1].c), window.index[-1]
        for bar in window.itertuples():
            hit = bar.l <= stop if side == 1 else bar.h >= stop
            if hit:
                exit_price, exit_time = stop, bar.Index
                break
        gross_return = side * (exit_price - row.entry) / row.entry
        adverse = max(0.0, max((row.entry - float(window.l.min())) / row.entry,
                               (float(window.h.max()) - row.entry) / row.entry))
        trades.append({"date": row.date.tz_convert("UTC"), "exit": exit_time.tz_convert("UTC"),
                       "gross_return": gross_return, "stop_fraction": stop_distance / row.entry,
                       "adverse_fraction": adverse})
    return pd.DataFrame(trades)


def metrics(trades: pd.DataFrame, cost_bps: float, economics: dict) -> dict:
    if trades.empty:
        return {"trades": 0, "profit_factor": 0, "expectancy_usdc": -99,
                "net_pnl_usdc": 0, "max_drawdown_pct": 100, "positive_year_ratio": 0,
                "maximum_effective_leverage": 0, "liquidation_count": 0}
    capital = economics["capital_usdc"]
    risk = capital * economics["risk_per_trade_pct"] / 100
    leverage = (risk / trades.stop_fraction / capital).clip(upper=economics["research_leverage_cap"])
    notional = capital * leverage
    pnl = notional * (trades.gross_return - cost_bps / 10000) - economics["opening_oracle_usdc"]
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = capital + pnl.cumsum()
    dd = (1 - equity / equity.cummax()).max()
    years = pd.Series(pnl.values, index=pd.DatetimeIndex(trades.date)).groupby(lambda value: value.year).sum()
    liquidation = (trades.adverse_fraction.values * leverage.values >= 1).sum()
    return {"trades": int(len(pnl)), "profit_factor": float(gains / losses) if losses else 99.0,
            "expectancy_usdc": float(pnl.mean()), "net_pnl_usdc": float(pnl.sum()),
            "max_drawdown_pct": float(max(0, dd) * 100),
            "positive_year_ratio": float((years > 0).mean()),
            "maximum_effective_leverage": float(leverage.max()), "liquidation_count": int(liquidation)}


def neighbors(point: tuple, passing: set[tuple], axes: list[list]) -> int:
    count = 0
    for index, axis in enumerate(axes):
        position = axis.index(point[index])
        for adjacent in (position - 1, position + 1):
            variant = list(point)
            if 0 <= adjacent < len(axis):
                variant[index] = axis[adjacent]
                count += tuple(variant) in passing
    return count


def run(source: Path, config: dict) -> dict:
    start, end = config["splits"]["train"]
    frame = load_m15(source).loc[start:end]
    signals = daily_signals(frame)
    axes = [config["search"]["shock_multiple_of_20d_median"],
            config["search"]["stop_multiple_of_signal_move"], config["search"]["exit_london_hour"]]
    economics, gate = config["economics"], config["train_gate"]
    evaluated = []
    for point in itertools.product(*axes):
        trades = simulate(signals, *point)
        scenarios = {name: metrics(trades, bps, economics) for name, bps in economics["roundtrip_bps"].items()}
        frictionless = dict(economics)
        frictionless["opening_oracle_usdc"] = 0
        gross_diagnostic = metrics(trades, 0, frictionless)
        base, stress = scenarios["base"], scenarios["stress"]
        passed = (base["trades"] >= gate["minimum_trades"]
                  and base["profit_factor"] >= gate["minimum_base_profit_factor"]
                  and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
                  and stress["expectancy_usdc"] >= gate["minimum_stress_expectancy_usdc"]
                  and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
                  and stress["max_drawdown_pct"] <= gate["maximum_drawdown_pct"]
                  and stress["liquidation_count"] == 0)
        evaluated.append({"parameters": {"shock_multiple": point[0], "stop_multiple": point[1],
                                          "exit_london_hour": point[2]},
                          "parameter_tuple": list(point), "scenarios": scenarios, "passes_numeric_gate": passed})
        evaluated[-1]["gross_no_cost_no_oracle_diagnostic"] = gross_diagnostic
    numeric = {tuple(row["parameter_tuple"]) for row in evaluated if row["passes_numeric_gate"]}
    for row in evaluated:
        row["stable_neighbors"] = neighbors(tuple(row["parameter_tuple"]), numeric, axes)
        row["passes_train_gate"] = (row["passes_numeric_gate"]
                                     and row["stable_neighbors"] >= gate["minimum_stable_neighbors"])
    survivors = [row for row in evaluated if row["passes_train_gate"]]
    return {"schema_version": 1, "campaign_id": config["campaign_id"], "stage": "pre_sq_falsification",
            "decision": "PASS_TO_SQ" if survivors else "REJECT_NO_SQ", "source": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "train_window": [start, end], "bars_loaded": int(len(frame)), "daily_observations": int(len(signals)),
            "attempted": len(evaluated), "survivor_count": len(survivors), "survivors": survivors,
            "all_results": evaluated, "validation_accessed": False, "oos_accessed": False,
            "holdout_accessed": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.config.read_bytes(); config = json.loads(raw)
    result = run(Path(config["source"]), config)
    result["config_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("decision", "attempted", "survivor_count",
                                                    "validation_accessed", "holdout_accessed")}, indent=2))


if __name__ == "__main__":
    main()
