#!/usr/bin/env python3
"""Train-only falsification for preregistered XAU abnormal-day momentum v36."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from lab.sq_bridge.build_xauusd_m15_cache import fingerprint
from lab.sq_bridge.spxusd_execution_economics import liquidation_distance_pct


def parameter_grid(config: dict[str, Any]) -> list[tuple[int, float, str, float]]:
    search = config["search"]
    points = list(itertools.product(
        search["lookback_sessions"], search["standard_deviations"],
        search["entry_time"], search["stop_fraction"],
    ))
    if len(points) != search["attempt_budget"]:
        raise ValueError("attempt budget does not match the frozen grid")
    return points


def assert_train_only(config: dict[str, Any]) -> None:
    if config.get("performance_accessed") is not False:
        raise ValueError("preregistered performance flag is not sealed")
    for name in ("validation_accessed", "oos_accessed", "holdout_evaluated"):
        if config.get(name) is not False:
            raise ValueError(f"train-only runner refuses opened {name}")


def cache_files(config: dict[str, Any], cache_root: Path) -> tuple[list[Path], list[dict]]:
    start, end = config["splits"]["train"]
    source_root = Path(config["source_root"])
    files, manifests = [], []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        cached = cache_root / f"year={year}" / "data.parquet"
        manifest_path = cached.with_suffix(".manifest.json")
        if not cached.is_file() or not manifest_path.is_file():
            raise FileNotFoundError(f"missing regenerable M15 cache for {year}")
        manifest = json.loads(manifest_path.read_text())
        source_files = sorted((source_root / f"year={year}").glob("month=*/data.parquet"))
        if not source_files or manifest.get("source_fingerprint") != fingerprint(source_files):
            raise ValueError(f"stale M15 cache for {year}")
        if manifest.get("output_sha256") != hashlib.sha256(cached.read_bytes()).hexdigest():
            raise ValueError(f"corrupt M15 cache for {year}")
        files.append(cached)
        manifests.append(manifest)
    return files, manifests


def load_m15(files: list[Path]) -> pd.DataFrame:
    import duckdb

    frame = duckdb.connect(":memory:").execute(
        'SELECT ts, open, high, low, "close", minute_count FROM read_parquet(?) ORDER BY ts',
        [[str(path) for path in files]],
    ).fetchdf()
    frame.index = pd.to_datetime(frame.pop("ts"), unit="s", utc=True)
    return frame


def session_records(frame: pd.DataFrame, entry_time: str) -> list[dict[str, Any]]:
    local = frame.index.tz_convert("America/New_York")
    lookup: dict[tuple[Any, str], pd.Timestamp | None] = {}
    for stamp, day, clock in zip(frame.index, local.date, local.strftime("%H:%M")):
        key = (day, clock)
        lookup[key] = stamp if key not in lookup else None
    entry_hour, entry_minute = map(int, entry_time.split(":"))
    cutoff_minutes = entry_hour * 60 + entry_minute - 15
    cutoff = f"{cutoff_minutes // 60:02d}:{cutoff_minutes % 60:02d}"
    records = []
    dates = sorted(day for (day, clock), stamp in lookup.items()
                   if clock == "16:45" and stamp is not None)
    for day in dates:
        stamps = (lookup.get((day - timedelta(days=1), "18:15")),
                  lookup.get((day, cutoff)), lookup.get((day, entry_time)),
                  lookup.get((day, "16:45")))
        if any(stamp is None for stamp in stamps):
            continue
        anchor_at, cutoff_at, entry_at, exit_at = stamps
        last_path_at = exit_at - pd.Timedelta(minutes=15)
        path = frame.loc[entry_at:last_path_at]
        required = pd.date_range(entry_at, last_path_at, freq="15min")
        selected = frame.loc[list(stamps)]
        if (selected.minute_count != 15).any() or not path.index.equals(required):
            continue
        if (path.minute_count != 15).any():
            continue
        anchor = float(frame.loc[anchor_at, "open"])
        records.append({
            "session_date": str(day), "anchor": anchor,
            "partial_return": float(frame.loc[cutoff_at, "close"]) / anchor - 1,
            "full_return": float(frame.loc[exit_at, "open"]) / anchor - 1,
            "entry_time": entry_at, "exit_time": exit_at,
            "entry": float(frame.loc[entry_at, "open"]), "exit": float(frame.loc[exit_at, "open"]),
            "path": path,
        })
    return records


def expected_session_counts(frame: pd.DataFrame, entry_time: str) -> dict[str, int]:
    local = frame.index.tz_convert("America/New_York")
    keys = set(zip(local.date, local.strftime("%H:%M")))
    entry_hour, entry_minute = map(int, entry_time.split(":"))
    cutoff_minutes = entry_hour * 60 + entry_minute - 15
    cutoff = f"{cutoff_minutes // 60:02d}:{cutoff_minutes % 60:02d}"
    counts: dict[str, int] = {}
    for day, clock in keys:
        if clock != "16:45":
            continue
        required = ((day - timedelta(days=1), "18:15"), (day, cutoff),
                    (day, entry_time), (day, "16:45"))
        if all(key in keys for key in required):
            year = str(day.year)
            counts[year] = counts.get(year, 0) + 1
    return counts


def coverage_gate(frame: pd.DataFrame, by_entry: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows, passed = {}, True
    for entry_time, records in by_entry.items():
        expected = expected_session_counts(frame, entry_time)
        complete: dict[str, int] = {}
        for record in records:
            year = record["session_date"][:4]
            complete[year] = complete.get(year, 0) + 1
        yearly = {year: {"expected": count, "complete": complete.get(year, 0),
                         "ratio": complete.get(year, 0) / count}
                  for year, count in sorted(expected.items())}
        total_expected, total_complete = sum(expected.values()), sum(complete.values())
        overall = total_complete / total_expected if total_expected else 0.0
        entry_pass = (overall >= 0.90 and bool(yearly)
                      and all(row["ratio"] >= 0.80 for row in yearly.values()))
        rows[entry_time] = {"expected": total_expected, "complete": total_complete,
                            "ratio": overall, "by_year": yearly, "pass": entry_pass}
        passed = passed and entry_pass
    return {"minimum_overall_ratio": 0.90, "minimum_each_year_ratio": 0.80,
            "by_entry": rows, "pass": passed}


def selected_leverage(stop: float, economics: dict[str, Any]) -> float:
    cap = int(1 / (stop * economics["liquidation_buffer_multiple_of_stop"]))
    return float(max(1, min(cap, economics["venue_max_leverage"])))


def simulate(record: dict[str, Any], side: int, stop: float,
             economics: dict[str, Any]) -> dict[str, Any]:
    entry = record["entry"]
    stop_price = entry * (1 - side * stop)
    leverage = selected_leverage(stop, economics)
    liquidation_fraction = liquidation_distance_pct(
        leverage, economics["venue_max_leverage"]) / 100
    exit_price, reason, liquidated = record["exit"], "time", False
    max_adverse = 0.0
    for row in record["path"].itertuples():
        adverse_open = max(0.0, side * (entry - float(row.open)) / entry)
        adverse_bar = max(0.0, ((entry - float(row.low)) / entry if side == 1
                                else (float(row.high) - entry) / entry))
        max_adverse = max(max_adverse, adverse_bar)
        if adverse_open >= liquidation_fraction:
            exit_price, reason, liquidated = float(row.open), "gap_liquidation", True
            break
        gap_stop = float(row.open) <= stop_price if side == 1 else float(row.open) >= stop_price
        if gap_stop:
            exit_price, reason = float(row.open), "gap_stop"
            break
        if liquidation_fraction <= stop and adverse_bar >= liquidation_fraction:
            exit_price = entry * (1 - side * liquidation_fraction)
            reason, liquidated = "intrabar_liquidation", True
            break
        hit_stop = float(row.low) <= stop_price if side == 1 else float(row.high) >= stop_price
        if hit_stop:
            exit_price, reason = stop_price, "stop"
            break
    return {
        "date": record["session_date"], "side": side, "entry": entry,
        "exit": exit_price, "gross_return": side * (exit_price / entry - 1),
        "max_adverse_fraction": max_adverse, "exit_reason": reason,
        "liquidated": liquidated, "selected_venue_leverage": leverage,
        "liquidation_fraction": liquidation_fraction,
    }


def trades_for(records: list[dict[str, Any]], lookback: int, deviations: float,
               stop: float, economics: dict[str, Any]) -> list[dict[str, Any]]:
    trades = []
    prior_full: list[float] = []
    for record in records:
        if len(prior_full) >= lookback:
            history = pd.Series(prior_full[-lookback:], dtype=float)
            mean, sigma = float(history.mean()), float(history.std(ddof=1))
            upper, lower = mean + deviations * sigma, mean - deviations * sigma
            partial = record["partial_return"]
            side = 1 if partial > upper else (-1 if partial < lower else 0)
            if side:
                trade = simulate(record, side, stop, economics)
                trade.update({"partial_return": partial, "threshold_mean": mean,
                              "threshold_sigma": sigma})
                trades.append(trade)
        # The current session becomes history only after its frozen 16:45 exit.
        prior_full.append(record["full_return"])
    return trades


def scenario_metrics(trades: list[dict[str, Any]], stop: float, name: str,
                     economics: dict[str, Any]) -> dict[str, Any]:
    if not trades:
        return {"trades": 0, "profit_factor": 0, "expectancy_usdc": -99,
                "net_pnl_usdc": 0, "max_drawdown_pct": 100,
                "positive_year_ratio": 0, "liquidation_count": 0}
    capital = float(economics["capital_usdc"])
    risk = capital * float(economics["risk_per_trade_pct"]) / 100
    notional = risk / stop
    leverage = selected_leverage(stop, economics)
    collateral = notional / leverage
    cost = notional * economics["roundtrip_bps"][name] / 10_000
    cost += economics["oracle_net_cost_usdc"][name]
    pnls = [(-collateral if row["liquidated"] else notional * row["gross_return"] - cost)
            for row in trades]
    series = pd.Series(pnls, dtype=float)
    gains, losses = series[series > 0].sum(), -series[series < 0].sum()
    equity = capital + series.cumsum()
    peak = pd.concat([pd.Series([capital]), equity]).cummax().iloc[1:].reset_index(drop=True)
    drawdown = float((1 - equity.reset_index(drop=True) / peak).max())
    years: dict[int, float] = {}
    for trade, pnl in zip(trades, pnls):
        year = int(trade["date"][:4])
        years[year] = years.get(year, 0) + pnl
    return {
        "trades": len(trades), "profit_factor": float(gains / losses) if losses else 99,
        "expectancy_usdc": float(series.mean()), "net_pnl_usdc": float(series.sum()),
        "max_drawdown_pct": max(0.0, drawdown * 100),
        "positive_year_ratio": sum(value > 0 for value in years.values()) / len(years),
        "positive_years": sum(value > 0 for value in years.values()),
        "observed_years": len(years), "liquidation_count": sum(row["liquidated"] for row in trades),
        "notional_usdc": notional, "exposure_multiple": notional / capital,
        "selected_venue_leverage": leverage, "margin_pct": collateral / capital * 100,
    }


def stable_neighbors(point: tuple, passing: set[tuple], axes: list[list]) -> int:
    neighbors = 0
    for index, axis in enumerate(axes):
        position = axis.index(point[index])
        for adjacent in (position - 1, position + 1):
            if 0 <= adjacent < len(axis):
                candidate = list(point)
                candidate[index] = axis[adjacent]
                neighbors += tuple(candidate) in passing
    return neighbors


def run(frame: pd.DataFrame, config: dict[str, Any], manifests: list[dict]) -> dict[str, Any]:
    assert_train_only(config)
    points = parameter_grid(config)
    economics, gate = config["economics"], config["train_gate"]
    by_entry = {entry: session_records(frame, entry) for entry in config["search"]["entry_time"]}
    coverage = coverage_gate(frame, by_entry)
    if not coverage["pass"]:
        return {
            "schema_version": 1, "stage": "discovery",
            "campaign_id": config["campaign_id"], "decision": "BLOCK",
            "block_reason": "INSUFFICIENT_HISTORICAL_SESSION_COVERAGE",
            "candidate_ids": [], "attempted": 0, "numeric_pass_count": 0,
            "survivor_count": 0, "survivors": [], "top_results": [], "all_results": [],
            "coverage_gate": coverage,
            "source_cache_manifests": manifests, "holdout_accessed": False,
            "validation_accessed": False, "oos_accessed": False,
            "performance_accessed": False, "live_authorized": False,
        }
    results = []
    for lookback, deviations, entry_time, stop in points:
        trades = trades_for(by_entry[entry_time], lookback, deviations, stop, economics)
        scenarios = {name: scenario_metrics(trades, stop, name, economics)
                     for name in ("base", "conservative", "stress")}
        base, stress = scenarios["base"], scenarios["stress"]
        numeric = (
            base["trades"] >= gate["minimum_trades"]
            and base["profit_factor"] >= gate["minimum_base_profit_factor"]
            and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
            and stress["expectancy_usdc"] >= gate["minimum_stress_expectancy_usdc"]
            and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
            and stress["max_drawdown_pct"] <= gate["maximum_drawdown_pct"]
            and stress["liquidation_count"] <= gate["maximum_liquidations"]
            and stress["margin_pct"] <= economics["maximum_margin_pct"]
        )
        point = (lookback, deviations, entry_time, stop)
        results.append({"candidate_id": f"xau-v36-{lookback}-{deviations}-{entry_time}-{stop}",
                        "parameters": {"lookback_sessions": lookback,
                                       "standard_deviations": deviations,
                                       "entry_time": entry_time, "stop_fraction": stop},
                        "parameter_tuple": list(point), "scenarios": scenarios,
                        "passes_numeric_gate": numeric})
    passing = {tuple(row["parameter_tuple"]) for row in results if row["passes_numeric_gate"]}
    axes = [config["search"][key] for key in
            ("lookback_sessions", "standard_deviations", "entry_time", "stop_fraction")]
    for row in results:
        row["stable_neighbors"] = stable_neighbors(tuple(row["parameter_tuple"]), passing, axes)
        row["passes_train_gate"] = (row["passes_numeric_gate"]
                                     and row["stable_neighbors"] >= gate["minimum_stable_neighbors"])
    survivors = [row for row in results if row["passes_train_gate"]]
    ranked = sorted(results, key=lambda row: (
        row["scenarios"]["stress"]["profit_factor"],
        row["scenarios"]["stress"]["expectancy_usdc"]), reverse=True)
    return {
        "schema_version": 1, "stage": "discovery", "campaign_id": config["campaign_id"],
        "decision": "PASS" if survivors else "REJECT", "candidate_ids": [
            row["candidate_id"] for row in survivors], "attempted": len(results),
        "numeric_pass_count": len(passing), "survivor_count": len(survivors),
        "survivors": survivors, "top_results": ranked[:10], "all_results": results,
        "session_counts_by_entry": {key: len(value) for key, value in by_entry.items()},
        "coverage_gate": coverage, "performance_accessed": True,
        "source_cache_manifests": manifests, "holdout_accessed": False,
        "validation_accessed": False, "oos_accessed": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.config.read_bytes()
    config = json.loads(raw)
    assert_train_only(config)
    files, manifests = cache_files(config, args.cache_root)
    result = run(load_m15(files), config, manifests)
    result["config_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("decision", "block_reason", "attempted", "numeric_pass_count",
                       "survivor_count", "session_counts_by_entry", "coverage_gate")
                      if key in result}, indent=2))


if __name__ == "__main__":
    main()
