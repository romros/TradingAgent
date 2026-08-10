#!/usr/bin/env python3
"""Train-only XAU execution falsification for CFTC managed-money flow v34."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

from lab.sq_bridge.xauusd_cftc_managed_money_v34 import (
    adjacent_neighbors, available_rows, load_positions, non_overlapping, raw_signals,
)
from lab.sq_bridge.build_xauusd_m15_cache import fingerprint


def train_files(root: Path, start: str, end: str) -> list[Path]:
    base = root / "XAUUSD" / "tf=1m"
    files = []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        files.extend(sorted((base / f"year={year}").glob("month=*/data.parquet")))
    if not files:
        raise FileNotFoundError(f"no train files under {base}")
    return files


def load_m15(files: list[Path], start: str, end: str) -> pd.DataFrame:
    import duckdb
    start_ts = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    end_ts = int((datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
                  + pd.Timedelta(days=1)).timestamp())
    query = """
      SELECT CAST(floor(ts/900)*900 AS BIGINT) ts,
             arg_min(open,ts) open, max(high) high, min(low) low,
             arg_max("close",ts) close_price, count(DISTINCT ts) minute_count
      FROM read_parquet(?, hive_partitioning=false)
      WHERE ts>=? AND ts<? GROUP BY 1 ORDER BY 1
    """
    connection = duckdb.connect(":memory:")
    connection.execute("SET threads=2")
    connection.execute("SET memory_limit='2GB'")
    connection.execute("SET preserve_insertion_order=false")
    frame = connection.execute(query, [[str(path) for path in files], start_ts, end_ts]
                               ).fetchdf().rename(columns={"close_price": "close"})
    connection.close()
    frame.index = pd.to_datetime(frame.ts, unit="s", utc=True)
    return frame


def validated_cache_files(cache_root: Path, source_root: Path, start: str, end: str) -> list[Path]:
    outputs = []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        output = cache_root / f"year={year}" / "data.parquet"
        manifest_path = output.with_suffix(".manifest.json")
        if not output.exists() or not manifest_path.exists():
            raise FileNotFoundError(f"missing M15 cache for {year}")
        manifest = json.loads(manifest_path.read_text())
        sources = sorted((source_root / "XAUUSD" / "tf=1m" / f"year={year}").glob("month=*/data.parquet"))
        if manifest["source_fingerprint"] != fingerprint(sources):
            raise ValueError(f"stale M15 cache for {year}")
        if manifest["output_sha256"] != hashlib.sha256(output.read_bytes()).hexdigest():
            raise ValueError(f"corrupt M15 cache for {year}")
        outputs.append(output)
    return outputs


def load_cached_m15(files: list[Path], start: str, end: str) -> pd.DataFrame:
    import duckdb
    start_ts = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    end_ts = int((datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
                  + pd.Timedelta(days=1)).timestamp())
    frame = duckdb.connect(":memory:").execute(
        'SELECT * FROM read_parquet(?) WHERE ts>=? AND ts<? ORDER BY ts',
        [[str(path) for path in files], start_ts, end_ts]).fetchdf()
    frame.index = pd.to_datetime(frame.ts, unit="s", utc=True)
    return frame


def first_bar(frame: pd.DataFrame, scheduled: pd.Timestamp, max_delay_hours: float) -> pd.Timestamp | None:
    index = frame.index.searchsorted(scheduled)
    if index >= len(frame.index):
        return None
    found = frame.index[index]
    return found if (found - scheduled).total_seconds() <= max_delay_hours * 3600 else None


def simulate(frame: pd.DataFrame, signal: dict[str, Any], config: dict[str, Any],
             scenario: str) -> dict[str, Any] | None:
    scheduled_entry = pd.Timestamp(signal["entry_at"])
    scheduled_exit = pd.Timestamp(signal["exit_at"])
    delay = float(config["execution"]["maximum_entry_delay_hours"])
    entry_time = first_bar(frame, scheduled_entry, delay)
    exit_time = first_bar(frame, scheduled_exit, delay)
    if entry_time is None or exit_time is None or exit_time <= entry_time:
        return None
    path = frame.loc[(frame.index >= entry_time) & (frame.index < exit_time)]
    if path.empty:
        return None
    gaps = path.index.to_series().diff().dt.total_seconds().div(3600).dropna()
    if not gaps.empty and gaps.max() > float(config["execution"]["maximum_allowed_source_gap_hours"]):
        return None
    side = int(signal["side"])
    entry = float(frame.loc[entry_time, "open"])
    stop_fraction = float(config["execution"]["stop_fraction"])
    stop_price = entry * (1 - side * stop_fraction)
    economics = config["economics"]
    notional = float(economics["notional_usdc"])
    leverage = float(economics["selected_venue_leverage"])
    max_leverage = float(economics["venue_max_leverage"])
    collateral = notional / leverage
    loss_capacity = collateral * (1 - leverage / max_leverage * .25)
    fixed_cost = notional * float(economics["roundtrip_bps"][scenario]) / 10_000
    fixed_cost += float(economics["oracle_net_cost_usdc_per_trade"])
    annual_carry = float(economics["annual_rollover_cost_pct"][scenario][
        "long" if side == 1 else "short"]) / 100
    exit_price = float(frame.loc[exit_time, "open"])
    actual_exit = exit_time
    reason, liquidated = "time", False
    opens = path.open.to_numpy(dtype=float)
    lows = path.low.to_numpy(dtype=float)
    highs = path.high.to_numpy(dtype=float)
    days_array = (path.index.view("int64") - entry_time.value) / 86_400_000_000_000
    carry_array = notional * annual_carry * days_array / 365.25
    liquidation_fraction = (loss_capacity - fixed_cost - carry_array) / notional
    adverse_open = np.maximum(0, side * (entry - opens) / entry)
    adverse_bar = ((entry - lows) / entry if side == 1 else (highs - entry) / entry)
    conditions = [liquidation_fraction <= 0,
                  adverse_open >= liquidation_fraction,
                  opens <= stop_price if side == 1 else opens >= stop_price,
                  (liquidation_fraction <= stop_fraction) & (adverse_bar >= liquidation_fraction),
                  lows <= stop_price if side == 1 else highs >= stop_price]
    hit = np.logical_or.reduce(conditions)
    if hit.any():
        index = int(np.flatnonzero(hit)[0])
        stamp = path.index[index]
        actual_exit = stamp
        if conditions[0][index]:
            exit_price, reason, liquidated = opens[index], "carry_liquidation", True
        elif conditions[1][index]:
            exit_price, reason, liquidated = opens[index], "gap_liquidation", True
        elif conditions[2][index]:
            exit_price, reason = opens[index], "gap_stop"
        elif conditions[3][index]:
            exit_price = entry * (1 - side * liquidation_fraction[index])
            reason, liquidated = "intrabar_liquidation", True
        else:
            exit_price, reason = stop_price, "stop"
    days = (actual_exit - entry_time).total_seconds() / 86400
    carry = notional * annual_carry * days / 365.25
    gross = side * (exit_price / entry - 1)
    pnl = -collateral if liquidated else notional * gross - fixed_cost - carry
    return {"entry_time": entry_time.isoformat(), "exit_time": actual_exit.isoformat(),
            "side": side, "gross_pnl_usdc": notional * gross, "net_pnl_usdc": pnl,
            "fixed_cost_usdc": fixed_cost, "carry_cost_usdc": carry,
            "holding_days": days, "exit_reason": reason, "liquidated": liquidated}


def metrics(trades: list[dict[str, Any]], capital: float) -> dict[str, Any]:
    if not trades:
        return {"trades": 0, "profit_factor": 0, "expectancy_usdc": -99,
                "net_pnl_usdc": 0, "max_drawdown_pct": 100,
                "positive_year_ratio": 0, "liquidation_count": 0}
    pnl = pd.Series([row["net_pnl_usdc"] for row in trades], dtype=float)
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = capital + pnl.cumsum()
    peak = pd.concat([pd.Series([capital]), equity]).cummax().iloc[1:].reset_index(drop=True)
    years: dict[int, float] = {}
    for row in trades:
        year = pd.Timestamp(row["entry_time"]).year
        years[year] = years.get(year, 0) + row["net_pnl_usdc"]
    return {"trades": len(trades), "profit_factor": float(gains / losses) if losses else 99,
            "expectancy_usdc": float(pnl.mean()), "net_pnl_usdc": float(pnl.sum()),
            "gross_pnl_usdc": sum(row["gross_pnl_usdc"] for row in trades),
            "max_drawdown_pct": float(max(0, (1 - equity.reset_index(drop=True) / peak).max()) * 100),
            "positive_year_ratio": sum(value > 0 for value in years.values()) / len(years),
            "positive_years": sum(value > 0 for value in years.values()),
            "observed_years": len(years),
            "liquidation_count": sum(row["liquidated"] for row in trades),
            "long_net_pnl_usdc": sum(row["net_pnl_usdc"] for row in trades if row["side"] == 1),
            "short_net_pnl_usdc": sum(row["net_pnl_usdc"] for row in trades if row["side"] == -1),
            "mean_holding_days": sum(row["holding_days"] for row in trades) / len(trades)}


def run(frame: pd.DataFrame, config: dict[str, Any], frequency: dict[str, Any],
        ledger: dict[str, Any], positions: dict[date, float], files: list[Path]) -> dict[str, Any]:
    if frequency.get("decision") != "PASS_TO_TRAIN_PERFORMANCE":
        raise ValueError("frequency gate did not authorize performance")
    if any(config.get(field) is not False for field in
           ("validation_accessed", "oos_accessed", "holdout_accessed",
            "sqcli_authorized", "paper_authorized", "live_authorized")):
        raise ValueError("future periods and trading must remain sealed")
    start, end = map(date.fromisoformat, config["splits"]["train"])
    rows = available_rows(ledger, positions, start, end)
    boundary = pd.Timestamp(end.isoformat(), tz="UTC") + pd.Timedelta(days=1)
    evaluated = []
    for point in map(tuple, frequency["performance_points"]):
        signals = non_overlapping(raw_signals(rows, int(point[0]), float(point[1])), int(point[2]))
        signals = [row for row in signals if pd.Timestamp(row["exit_at"]) <= boundary]
        scenarios, skipped = {}, 0
        for scenario in ("base", "conservative", "stress"):
            trades = []
            for signal in signals:
                trade = simulate(frame, signal, config, scenario)
                if trade is None:
                    skipped += 1
                else:
                    trades.append(trade)
            scenarios[scenario] = metrics(trades, float(config["economics"]["capital_usdc"]))
        gate = config["train_performance_gate"]
        base, conservative, stress = (scenarios[key] for key in ("base", "conservative", "stress"))
        numeric = (stress["trades"] >= gate["minimum_trades"]
                   and base["profit_factor"] >= gate["minimum_base_profit_factor"]
                   and conservative["profit_factor"] >= gate["minimum_conservative_profit_factor"]
                   and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
                   and stress["expectancy_usdc"] >= gate["minimum_stress_expectancy_usdc"]
                   and stress["positive_year_ratio"] >= gate["minimum_stress_positive_year_ratio"]
                   and stress["max_drawdown_pct"] <= gate["maximum_stress_drawdown_pct"]
                   and stress["liquidation_count"] <= gate["maximum_liquidations"])
        evaluated.append({"parameter_tuple": list(point), "planned_trades": len(signals),
                          "missing_scenarios": skipped, "scenarios": scenarios,
                          "passes_numeric_train_gate": numeric})
    passing = {tuple(row["parameter_tuple"]) for row in evaluated if row["passes_numeric_train_gate"]}
    axes = [config["search"][key] for key in
            ("lookback_weeks", "net_change_threshold_open_interest_pct_points", "hold_weeks")]
    for row in evaluated:
        row["stable_neighbors"] = adjacent_neighbors(tuple(row["parameter_tuple"]), passing, axes)
        row["passes_train_gate"] = (row["passes_numeric_train_gate"] and
                                     row["stable_neighbors"] >= gate["minimum_stable_neighbors"])
    survivors = [row for row in evaluated if row["passes_train_gate"]]
    return {"schema_version": 1, "campaign_id": config["campaign_id"],
            "stage": "train_performance", "decision": "PASS_TO_SQ" if survivors else "REJECT_NO_SQ",
            "train_window": [start.isoformat(), end.isoformat()], "attempted": len(evaluated),
            "survivor_count": len(survivors), "survivors": survivors, "all_results": evaluated,
            "m15_bars": len(frame), "source_files": [str(path) for path in files],
            "xau_performance_accessed": True, "validation_accessed": False,
            "oos_accessed": False, "holdout_accessed": False, "sqcli_used": False,
            "paper_authorized": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--frequency", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_raw, frequency_raw = args.config.read_bytes(), args.frequency.read_bytes()
    config, frequency = json.loads(config_raw), json.loads(frequency_raw)
    ledger_raw = Path(config["availability_ledger"]).read_bytes()
    ledger = json.loads(ledger_raw)
    start, end = config["splits"]["train"]
    position_paths = [path for path in sorted(Path().glob(config["position_source_glob"]))
                      if int(path.stem.rsplit("_", 1)[1]) <= int(end[:4])]
    positions = load_positions(position_paths, config["expected_identity"])
    source_root = Path(config["xau_source"]["root"])
    files = validated_cache_files(Path(config["xau_source"]["m15_cache_root"]),
                                  source_root, start, end)
    result = run(load_cached_m15(files, start, end), config, frequency, ledger, positions, files)
    result["config_sha256"] = hashlib.sha256(config_raw).hexdigest()
    result["frequency_sha256"] = hashlib.sha256(frequency_raw).hexdigest()
    result["ledger_sha256"] = hashlib.sha256(ledger_raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("decision", "m15_bars", "attempted", "survivor_count")}, indent=2))


if __name__ == "__main__":
    main()
