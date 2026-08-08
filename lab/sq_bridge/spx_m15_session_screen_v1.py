#!/usr/bin/env python3
"""Cheap preregistered SPX session screen before any SQ Builder campaign."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


PERIODS = {
    "development": (2012, 2018),
    "validation": (2019, 2022),
}
COSTS_BPS = (8.0, 15.0, 30.0)


def profit_factor(values) -> float | None:
    gains = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    return gains / losses if losses else None


def metrics(frame, return_column: str, cost_bps: float) -> dict:
    values = frame[return_column].dropna() - cost_bps / 10_000.0
    years = frame.loc[values.index, "year"]
    yearly = values.groupby(years).sum()
    return {
        "trades": int(len(values)),
        "mean_net_bps": round(float(values.mean() * 10_000), 6) if len(values) else None,
        "profit_factor": round(profit_factor(values), 6) if len(values) and profit_factor(values) is not None else None,
        "net_return_sum_pct": round(float(values.sum() * 100), 6),
        "positive_years": int((yearly > 0).sum()),
        "years": int(len(yearly)),
    }


def load_daily(parquet: Path):
    import duckdb
    return duckdb.connect(":memory:").execute("""
      WITH bars AS (
        SELECT *, to_timestamp(ts) AT TIME ZONE 'America/New_York' AS local_ts,
          CAST(to_timestamp(ts) AT TIME ZONE 'America/New_York' AS DATE) AS day
        FROM read_parquet(?)
        WHERE year(to_timestamp(ts) AT TIME ZONE 'America/New_York') <= 2026
      ), daily AS (
        SELECT day,
          arg_min(open, local_ts) FILTER (WHERE CAST(local_ts AS TIME) BETWEEN TIME '09:30' AND TIME '09:35') AS open_0930,
          arg_max(close, local_ts) FILTER (WHERE CAST(local_ts AS TIME) <= TIME '10:00') AS close_1000,
          arg_max(close, local_ts) FILTER (WHERE CAST(local_ts AS TIME) <= TIME '10:30') AS close_1030,
          arg_max(close, local_ts) FILTER (WHERE CAST(local_ts AS TIME) <= TIME '15:30') AS close_1530,
          arg_max(close, local_ts) FILTER (WHERE CAST(local_ts AS TIME) <= TIME '15:59') AS close_1559
        FROM bars GROUP BY day
      )
      SELECT *, lag(close_1559) OVER (ORDER BY day) AS previous_close
      FROM daily ORDER BY day
    """, [str(parquet)]).fetchdf()


def screen(parquet: Path) -> dict:
    import numpy as np
    frame = load_daily(parquet)
    frame["year"] = frame.day.dt.year
    frame["weekday"] = frame.day.dt.weekday
    day_filters = {
        "all": frame.weekday <= 4,
        "no_monday": frame.weekday.between(1, 4),
        "no_friday": frame.weekday.between(0, 3),
        "tue_thu": frame.weekday.between(1, 3),
    }
    candidates = []
    variants = []
    definitions = [("gap", "open_0930", "previous_close")]
    definitions += [(f"drive_{entry[-4:]}", entry, "open_0930") for entry in ("close_1000", "close_1030")]
    for (mechanism, entry, reference), exit_col, style, direction, day_name in itertools.product(
            definitions, ("close_1530", "close_1559"), ("continuation", "fade"),
            ("both", "long_only", "short_only"), day_filters):
        raw_signal = np.sign(frame[entry] / frame[reference] - 1)
        signal = raw_signal if style == "continuation" else -raw_signal
        if direction == "long_only": signal = signal.where(signal > 0)
        if direction == "short_only": signal = signal.where(signal < 0)
        column = "strategy_return"
        test = frame.loc[day_filters[day_name]].copy()
        test[column] = signal.loc[test.index] * (test[exit_col] / test[entry] - 1)
        variant_id = f"{mechanism}_{exit_col[-4:]}_{style}_{direction}_{day_name}"
        result = {"id": variant_id, "mechanism": mechanism, "entry": entry, "exit": exit_col,
                  "style": style, "direction": direction, "days": day_name, "periods": {}}
        for period, (start, end) in PERIODS.items():
            segment = test[test.year.between(start, end)]
            result["periods"][period] = {str(cost): metrics(segment, column, cost) for cost in COSTS_BPS}
        dev = result["periods"]["development"]["15.0"]
        val = result["periods"]["validation"]["15.0"]
        result["development_pass"] = bool(dev["trades"] >= 300 and (dev["profit_factor"] or 0) >= 1.15
                                                  and dev["positive_years"] >= 5)
        result["validation_pass"] = bool(result["development_pass"] and val["trades"] >= 150
                                         and (val["profit_factor"] or 0) >= 1.10
                                         and val["positive_years"] >= 3)
        if result["validation_pass"]:
            result["periods"]["oos"] = {str(cost): metrics(
                test[test.year.between(2023, 2025)], column, cost) for cost in COSTS_BPS}
        variants.append(result)
        if result["validation_pass"]:
            candidates.append(result)
    ranked = sorted(variants, key=lambda row: (
        row["validation_pass"], row["periods"]["validation"]["15.0"]["mean_net_bps"] or -999), reverse=True)
    return {
        "schema_version": 1,
        "family": "spx_m15_session_gap_and_opening_drive_v1",
        "source": str(parquet),
        "attempted": len(variants),
        "costs_bps": list(COSTS_BPS),
        "periods": PERIODS,
        "sealed_holdout": "2026-01-01/2026-07-08 (not evaluated)",
        "oos_policy": "2023-2025 is evaluated only for validation survivors",
        "audit_warning": "An initial local run evaluated 2023-2025 for all variants; those numbers were discarded and the period is contaminated for this family.",
        "development_survivors": sum(row["development_pass"] for row in variants),
        "validation_survivors": len(candidates),
        "top_five": ranked[:5],
        "candidates": candidates,
        "decision": "CONTINUE_TO_OOS_REVIEW" if candidates else "REJECT_FAMILY_BEFORE_SQ",
        "sqcli_executed": False,
        "paper_or_live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = screen(args.parquet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("attempted", "development_survivors",
                                                   "validation_survivors", "decision")}, indent=2))


if __name__ == "__main__":
    main()
