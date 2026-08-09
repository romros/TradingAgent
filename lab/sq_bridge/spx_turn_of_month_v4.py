#!/usr/bin/env python3
"""Development-only SPX turn-of-month institutional-flow screen."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


def profit_factor(values) -> float | None:
    gains = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    return gains / losses if losses else None


def load_development_daily(parquet: Path):
    import duckdb
    return duckdb.connect(":memory:").execute("""
      WITH bars AS (
        SELECT *, to_timestamp(ts) AT TIME ZONE 'America/New_York' AS local_ts,
          CAST(to_timestamp(ts) AT TIME ZONE 'America/New_York' AS DATE) AS day
        FROM read_parquet(?)
        WHERE year(to_timestamp(ts) AT TIME ZONE 'America/New_York') BETWEEN 2012 AND 2018
      )
      SELECT day,
        arg_max(close, local_ts) FILTER (
          WHERE CAST(local_ts AS TIME) <= TIME '15:59'
        ) AS close_1559
      FROM bars
      GROUP BY day
      HAVING close_1559 IS NOT NULL
      ORDER BY day
    """, [str(parquet)]).fetchdf()


def build_trades(frame, entry_from_month_end: int, exit_day_next_month: int):
    import pandas as pd
    work = frame.copy()
    work["day"] = pd.to_datetime(work["day"])
    work = work[(work.day.dt.weekday < 5) & work.close_1559.notna()].sort_values("day")
    work["month"] = work.day.dt.to_period("M")
    groups = {month: group.reset_index(drop=True) for month, group in work.groupby("month")}
    trades = []
    for month in sorted(groups):
        next_month = month + 1
        if next_month not in groups:
            continue
        current, following = groups[month], groups[next_month]
        entry_index = len(current) - 1 + entry_from_month_end
        exit_index = exit_day_next_month - 1
        if entry_index < 0 or exit_index >= len(following):
            continue
        entry, exit_ = current.iloc[entry_index], following.iloc[exit_index]
        trades.append({
            "entry_day": entry.day.date().isoformat(),
            "exit_day": exit_.day.date().isoformat(),
            "year": int(entry.day.year),
            "gross_return": float(exit_.close_1559 / entry.close_1559 - 1.0),
            "holding_days": int((exit_.day - entry.day).days),
        })
    return trades


def metrics(trades: list[dict], cost_bps: float) -> dict:
    import pandas as pd
    frame = pd.DataFrame(trades)
    if frame.empty:
        return {"trades": 0, "profit_factor": None, "mean_net_bps": None,
                "net_return_sum_pct": 0.0, "positive_years": 0, "years": 0,
                "mean_holding_days": None}
    values = frame.gross_return - cost_bps / 10_000.0
    yearly = values.groupby(frame.year).sum()
    return {
        "trades": int(len(values)),
        "profit_factor": round(profit_factor(values), 6) if profit_factor(values) is not None else None,
        "mean_net_bps": round(float(values.mean() * 10_000), 6),
        "net_return_sum_pct": round(float(values.sum() * 100), 6),
        "positive_years": int((yearly > 0).sum()),
        "years": int(len(yearly)),
        "mean_holding_days": round(float(frame.holding_days.mean()), 3),
    }


def run(parquet: Path, config: dict) -> dict:
    frame = load_development_daily(parquet)
    costs = config["costs_bps"]
    gate = config["development_gate"]
    rows = []
    for entry_offset, exit_day in itertools.product(
        config["grid"]["entry_from_month_end"], config["grid"]["exit_day_next_month"]
    ):
        trades = build_trades(frame, entry_offset, exit_day)
        measured = {name: metrics(trades, value) for name, value in costs.items()}
        base, stress = measured["base"], measured["stress"]
        passes = (
            stress["trades"] >= gate["minimum_trades"]
            and stress["positive_years"] >= gate["minimum_positive_years"]
            and (base["profit_factor"] or 0) >= gate["minimum_base_profit_factor"]
            and (stress["profit_factor"] or 0) >= gate["minimum_stress_profit_factor"]
            and (base["mean_net_bps"] or -999) >= gate["minimum_base_mean_net_bps"]
        )
        rows.append({
            "parameters": {"entry_from_month_end": entry_offset, "exit_day_next_month": exit_day},
            "metrics": measured,
            "passes_numeric_gate": bool(passes),
        })

    numeric = [row for row in rows if row["passes_numeric_gate"]]
    passing_points = {
        (row["parameters"]["entry_from_month_end"], row["parameters"]["exit_day_next_month"])
        for row in numeric
    }
    for row in rows:
        point = (row["parameters"]["entry_from_month_end"], row["parameters"]["exit_day_next_month"])
        neighbours = {(point[0] - 1, point[1]), (point[0] + 1, point[1]),
                      (point[0], point[1] - 1), (point[0], point[1] + 1)}
        row["has_passing_neighbour"] = bool(neighbours & passing_points)
        row["passes_stability_gate"] = bool(row["passes_numeric_gate"] and row["has_passing_neighbour"])
    stable = [row for row in rows if row["passes_stability_gate"]]
    ranked = sorted(rows, key=lambda row: (
        row["passes_stability_gate"], row["metrics"]["stress"]["profit_factor"] or 0,
        row["metrics"]["base"]["mean_net_bps"] or -999,
    ), reverse=True)
    return {
        "schema_version": 1,
        "family": config["id"],
        "hypothesis": config["hypothesis"],
        "source": str(parquet),
        "development": "2012-01-01/2018-12-31",
        "validation": "2019-01-01/2022-12-31 (not loaded)",
        "contaminated_prior_period": "2023-01-01/2025-12-31 (not loaded)",
        "sealed_holdout": "2026-01-01/2026-07-08 (not loaded)",
        "attempted": len(rows),
        "numeric_passes": len(numeric),
        "stable_passes": len(stable),
        "top_five": ranked[:5],
        "passing": stable,
        "validation_accessed": False,
        "holdout_accessed": False,
        "sqcli_executed": False,
        "decision": "CONTINUE_TO_PREREGISTERED_VALIDATION" if stable else "REJECT_FAMILY_BEFORE_VALIDATION",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.parquet, json.loads(args.config.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("attempted", "numeric_passes", "stable_passes", "decision")}, indent=2))


if __name__ == "__main__":
    main()
