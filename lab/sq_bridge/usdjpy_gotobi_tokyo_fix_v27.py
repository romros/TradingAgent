#!/usr/bin/env python3
"""Train-only falsification screen for USDJPY Gotobi/Tokyo-fix v27."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from calendar import monthrange
from pathlib import Path

import pandas as pd

from lab.sq_bridge.gbpusd_m15_v1 import load_m15


def event_dates(available_dates: set, mode: str) -> set:
    if mode not in {"exact_calendar", "weekend_previous_business_day"}:
        raise ValueError("unknown event mode")
    if not available_dates:
        return set()
    start, end = min(available_dates), max(available_dates)
    months = pd.period_range(start, end, freq="M")
    result = set()
    for month in months:
        for day in (5, 10, 15, 20, 25, 30):
            if day > monthrange(month.year, month.month)[1]:
                continue
            target = pd.Timestamp(month.year, month.month, day).date()
            if mode == "exact_calendar":
                if target in available_dates:
                    result.add(target)
                continue
            shifted = target
            while pd.Timestamp(shifted).weekday() >= 5:
                shifted -= pd.Timedelta(days=1)
            if shifted in available_dates:
                result.add(shifted)
    return result


def daily_windows(frame: pd.DataFrame, entry_hour: int, exit_hour: int) -> pd.DataFrame:
    local = frame.copy(); local.index = local.index.tz_convert("Asia/Tokyo")
    rows = []
    for date, day in local.groupby(local.index.date, sort=False):
        entry_rows = day[(day.index.hour == entry_hour) & (day.index.minute == 0)]
        exit_rows = day[(day.index.hour == exit_hour) & (day.index.minute == 0)]
        if len(entry_rows) != 1 or len(exit_rows) != 1:
            continue
        entry_time, exit_time = entry_rows.index[0], exit_rows.index[0]
        path = day[(day.index >= entry_time) & (day.index < exit_time)]
        if len(path) != (exit_hour - entry_hour) * 4:
            continue
        entry, exit_price = float(entry_rows.iloc[0].o), float(exit_rows.iloc[0].o)
        rows.append({"date": date, "entry_time": entry_time.tz_convert("UTC"), "entry": entry,
                     "exit": exit_price, "low": float(path.l.min()), "high": float(path.h.max())})
    return pd.DataFrame(rows)


def simulate(windows: pd.DataFrame, events: set, stop_fraction: float) -> pd.DataFrame:
    rows = []
    for row in windows.itertuples():
        if row.date not in events:
            continue
        stop = row.entry * (1 - stop_fraction)
        stopped = row.low <= stop
        exit_price = stop if stopped else row.exit
        rows.append({"date": row.entry_time, "gross_return": exit_price / row.entry - 1,
                     "adverse_fraction": max(0, (row.entry - row.low) / row.entry),
                     "stop_fraction": stop_fraction})
    return pd.DataFrame(rows)


def metrics(trades: pd.DataFrame, cost_bps: float, oracle_cost: float, economics: dict) -> dict:
    if trades.empty:
        return {"trades": 0, "profit_factor": 0, "expectancy_usdc": -99,
                "net_pnl_usdc": 0, "max_drawdown_pct": 100, "positive_year_ratio": 0,
                "effective_leverage": 0, "liquidation_count": 0}
    capital = economics["capital_usdc"]
    risk = capital * economics["risk_per_trade_pct"] / 100
    leverage = min(risk / trades.stop_fraction.iloc[0] / capital, economics["research_leverage_cap"])
    pnl = capital * leverage * (trades.gross_return - cost_bps / 10_000) - oracle_cost
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = capital + pnl.cumsum(); dd = (1 - equity / equity.cummax()).max()
    years = pd.Series(pnl.values, index=pd.DatetimeIndex(trades.date)).groupby(lambda value: value.year).sum()
    return {"trades": int(len(pnl)), "profit_factor": float(gains / losses) if losses else 99.0,
            "expectancy_usdc": float(pnl.mean()), "net_pnl_usdc": float(pnl.sum()),
            "max_drawdown_pct": float(max(0, dd) * 100),
            "positive_year_ratio": float((years > 0).mean()), "effective_leverage": float(leverage),
            "liquidation_count": int((trades.adverse_fraction * leverage >= 1).sum())}


def stable_neighbors(point: tuple, passing: set[tuple], axes: list[list]) -> int:
    count = 0
    for index, axis in enumerate(axes):
        position = axis.index(point[index])
        for adjacent in (position - 1, position + 1):
            if 0 <= adjacent < len(axis):
                candidate = list(point); candidate[index] = axis[adjacent]
                count += tuple(candidate) in passing
    return count


def run(source: Path, config: dict) -> dict:
    start, end = config["splits"]["train"]
    frame = load_m15(source).loc[start:end]
    axes = [config["search"]["event_mode"], config["search"]["entry_jst_hour"],
            config["search"]["stop_fraction"]]
    economics, gate = config["economics"], config["train_gate"]
    windows_by_hour = {hour: daily_windows(frame, hour, config["search"]["exit_jst_hour"])
                       for hour in axes[1]}
    evaluated = []
    for point in itertools.product(*axes):
        mode, entry_hour, stop = point; windows = windows_by_hour[entry_hour]
        events = event_dates(set(windows.date), mode)
        trades = simulate(windows, events, stop)
        scenarios = {name: metrics(trades, bps, economics["oracle_net_cost_usdc"][name], economics)
                     for name, bps in economics["roundtrip_bps"].items()}
        non_event = windows[~windows.date.isin(events)]
        event_gross_bps = float(trades.gross_return.mean() * 10_000) if not trades.empty else -999
        non_event_gross_bps = float((non_event.exit / non_event.entry - 1).mean() * 10_000) if not non_event.empty else 0
        excess = event_gross_bps - non_event_gross_bps
        base, stress = scenarios["base"], scenarios["stress"]
        passed = (base["trades"] >= gate["minimum_trades"]
                  and base["profit_factor"] >= gate["minimum_base_profit_factor"]
                  and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
                  and stress["expectancy_usdc"] >= gate["minimum_stress_expectancy_usdc"]
                  and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
                  and stress["max_drawdown_pct"] <= gate["maximum_drawdown_pct"]
                  and stress["liquidation_count"] == 0
                  and excess >= gate["minimum_gross_excess_vs_non_event_bps"])
        evaluated.append({"parameters": {"event_mode": mode, "entry_jst_hour": entry_hour,
                                          "stop_fraction": stop}, "parameter_tuple": list(point),
                          "event_gross_bps": event_gross_bps, "non_event_gross_bps": non_event_gross_bps,
                          "gross_excess_vs_non_event_bps": excess, "scenarios": scenarios,
                          "passes_numeric_gate": passed})
    numeric = {tuple(row["parameter_tuple"]) for row in evaluated if row["passes_numeric_gate"]}
    for row in evaluated:
        row["stable_neighbors"] = stable_neighbors(tuple(row["parameter_tuple"]), numeric, axes)
        row["passes_train_gate"] = (row["passes_numeric_gate"]
                                     and row["stable_neighbors"] >= gate["minimum_stable_neighbors"])
    survivors = [row for row in evaluated if row["passes_train_gate"]]
    return {"schema_version": 1, "campaign_id": config["campaign_id"], "stage": "pre_sq_falsification",
            "decision": "PASS_TO_SQ" if survivors else "REJECT_NO_SQ", "source": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "train_window": [start, end],
            "bars_loaded": int(len(frame)), "attempted": len(evaluated), "survivor_count": len(survivors),
            "survivors": survivors, "all_results": evaluated, "validation_accessed": False,
            "oos_accessed": False, "holdout_accessed": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    raw = args.config.read_bytes(); config = json.loads(raw); result = run(Path(config["source"]), config)
    result["config_sha256"] = hashlib.sha256(raw).hexdigest(); args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("decision", "attempted", "survivor_count",
                                                    "validation_accessed", "holdout_accessed")}, indent=2))


if __name__ == "__main__":
    main()
