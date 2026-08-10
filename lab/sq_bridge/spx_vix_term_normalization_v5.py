#!/usr/bin/env python3
"""Development-only SPX screen after VIX9D/VIX3M inversion normalizes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_signals(vix_root: Path):
    import pandas as pd
    short = pd.read_csv(vix_root / "VIX9D_History.csv", parse_dates=["DATE"])[["DATE", "CLOSE"]]
    long = pd.read_csv(vix_root / "VIX3M_History.csv", parse_dates=["DATE"])[["DATE", "CLOSE"]]
    frame = short.rename(columns={"CLOSE": "vix9d"}).merge(
        long.rename(columns={"CLOSE": "vix3m"}), on="DATE", how="inner", validate="one_to_one"
    ).sort_values("DATE")
    frame = frame[frame.DATE.dt.year.between(2012, 2018)].copy()
    frame["ratio"] = frame.vix9d / frame.vix3m
    frame["signal"] = (frame.ratio.shift(1) > 1.0) & (frame.ratio <= 1.0)
    return frame.loc[frame.signal, ["DATE", "ratio"]].reset_index(drop=True)


def load_spx_development(parquet: Path):
    import duckdb
    return duckdb.connect(":memory:").execute("""
      WITH bars AS (
        SELECT to_timestamp(ts) AT TIME ZONE 'America/New_York' AS local_ts, close
        FROM read_parquet(?)
        WHERE year(to_timestamp(ts) AT TIME ZONE 'America/New_York') BETWEEN 2012 AND 2018
      )
      SELECT CAST(local_ts AS DATE) AS day, arg_max(close, local_ts) AS close_1545
      FROM bars
      WHERE CAST(local_ts AS TIME) BETWEEN TIME '15:45' AND TIME '15:45:59'
      GROUP BY day ORDER BY day
    """, [str(parquet)]).fetchdf()


def build_trades(spx, signals, holding_sessions: int):
    import pandas as pd
    prices = spx.copy().sort_values("day").reset_index(drop=True)
    prices["day"] = pd.to_datetime(prices.day)
    signal_days = sorted(pd.to_datetime(signals.DATE).tolist())
    trades = []
    last_exit_index = -1
    for signal_day in signal_days:
        eligible = prices.index[prices.day > signal_day]
        if len(eligible) == 0:
            continue
        entry_i = int(eligible[0])
        exit_i = entry_i + holding_sessions
        if entry_i <= last_exit_index or exit_i >= len(prices):
            continue
        entry, exit_ = prices.iloc[entry_i], prices.iloc[exit_i]
        if (entry.day - signal_day).days > 4:
            continue
        trades.append({
            "signal_day": signal_day.date().isoformat(),
            "entry_day": entry.day.date().isoformat(),
            "exit_day": exit_.day.date().isoformat(),
            "year": int(entry.day.year),
            "gross_return": float(exit_.close_1545 / entry.close_1545 - 1.0),
            "holding_calendar_days": int((exit_.day - entry.day).days),
        })
        last_exit_index = exit_i
    return trades


def profit_factor(values) -> float | None:
    gains = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    return gains / losses if losses else None


def metrics(trades: list[dict], cost_bps: float) -> dict:
    import pandas as pd
    frame = pd.DataFrame(trades)
    if frame.empty:
        return {"trades": 0, "profit_factor": None, "mean_net_bps": None,
                "net_return_sum_pct": 0.0, "positive_years": 0, "years": 0}
    net = frame.gross_return - cost_bps / 10_000.0
    yearly = net.groupby(frame.year).sum()
    pf = profit_factor(net)
    return {
        "trades": int(len(net)),
        "profit_factor": round(pf, 6) if pf is not None else None,
        "mean_net_bps": round(float(net.mean() * 10_000), 6),
        "net_return_sum_pct": round(float(net.sum() * 100), 6),
        "positive_years": int((yearly > 0).sum()),
        "years": int(len(yearly)),
        "mean_holding_calendar_days": round(float(frame.holding_calendar_days.mean()), 3),
        "worst_net_trade_pct": round(float(net.min() * 100), 6),
    }


def run(parquet: Path, vix_root: Path, config: dict) -> dict:
    signals = load_signals(vix_root)
    spx = load_spx_development(parquet)
    gate, costs = config["development_gate"], config["costs_bps"]
    rows = []
    for holding in config["grid"]["holding_sessions"]:
        trades = build_trades(spx, signals, holding)
        measured = {name: metrics(trades, bps) for name, bps in costs.items()}
        base, stress = measured["base"], measured["stress"]
        passed = (
            stress["trades"] >= gate["minimum_trades"]
            and stress["positive_years"] >= gate["minimum_positive_years"]
            and (base["profit_factor"] or 0) >= gate["minimum_base_profit_factor"]
            and (stress["profit_factor"] or 0) >= gate["minimum_stress_profit_factor"]
            and (base["mean_net_bps"] or -999) >= gate["minimum_base_mean_net_bps"]
        )
        rows.append({"holding_sessions": holding, "metrics": measured, "passes_numeric_gate": bool(passed)})
    passing = {row["holding_sessions"] for row in rows if row["passes_numeric_gate"]}
    stable = any({left, right} <= passing for left, right in zip(
        config["grid"]["holding_sessions"], config["grid"]["holding_sessions"][1:]
    ))
    return {
        "schema_version": 1,
        "family": config["id"],
        "hypothesis": config["hypothesis"],
        "source_spx": str(parquet),
        "source_vix_root": str(vix_root),
        "development": "2012-01-01/2018-12-31",
        "signal_events": int(len(signals)),
        "attempted": len(rows),
        "results": rows,
        "numeric_passes": len(passing),
        "stable_region_pass": stable,
        "validation": "2019-2022 (not loaded)",
        "contaminated_prior_period": "2023-2025 (not loaded)",
        "sealed_holdout": "2026 (not loaded)",
        "validation_accessed": False,
        "holdout_accessed": False,
        "sqcli_executed": False,
        "leverage_selected": False,
        "decision": "CONTINUE_TO_PREREGISTERED_VALIDATION" if stable else "REJECT_FAMILY_BEFORE_VALIDATION",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--vix-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.parquet, args.vix_root, json.loads(args.config.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("signal_events", "attempted", "numeric_passes", "stable_region_pass", "decision")}, indent=2))


if __name__ == "__main__":
    main()
