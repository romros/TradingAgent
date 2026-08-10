#!/usr/bin/env python3
"""Train-only XAU performance falsification for macro regime v30b survivors."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from lab.sq_bridge.xauusd_real_yield_dollar_v30b import (
    adjacent_neighbors, episodes, load_series, states, weekly_latest,
)


def assert_train_only(config: dict[str, Any], macro_gate: dict[str, Any]) -> None:
    if macro_gate.get("decision") != "PASS_TO_TRAIN_PERFORMANCE":
        raise ValueError("macro frequency gate did not authorize train performance")
    if any(config.get(field) is not False for field in
           ("validation_accessed", "oos_accessed", "holdout_accessed",
            "sqcli_authorized", "paper_authorized", "live_authorized")):
        raise ValueError("train runner requires future periods, SQ and trading to remain sealed")


def train_files(root: Path, start: str, end: str) -> list[Path]:
    base = root / "XAUUSD" / "tf=1m"
    files = []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        files.extend(sorted((base / f"year={year}").glob("month=*/data.parquet")))
    if not files:
        raise FileNotFoundError(f"no XAUUSD files under {base}")
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
    frame = duckdb.connect(":memory:").execute(
        query, [[str(path) for path in files], start_ts, end_ts]
    ).fetchdf().rename(columns={"close_price": "close"})
    frame.index = pd.to_datetime(frame.ts, unit="s", utc=True)
    return frame


def complete_entry_bar(frame: pd.DataFrame, stamp: pd.Timestamp) -> bool:
    return stamp in frame.index and int(frame.loc[stamp, "minute_count"]) >= 1


def simulate_episode(frame: pd.DataFrame, episode: dict[str, Any], exit_time: pd.Timestamp,
                     config: dict[str, Any], scenario: str) -> dict[str, Any] | None:
    entry_time = pd.Timestamp(episode["decision_time_utc"])
    if not complete_entry_bar(frame, entry_time) or not complete_entry_bar(frame, exit_time):
        return None
    path = frame.loc[(frame.index >= entry_time) & (frame.index < exit_time)]
    if path.empty or (path.minute_count < 1).any():
        return None
    gaps = path.index.to_series().diff().dt.total_seconds().div(3600).dropna()
    if not gaps.empty and gaps.max() > float(config["execution"]["maximum_allowed_source_gap_hours"]):
        return None
    side = int(episode["side"])
    entry = float(frame.loc[entry_time, "open"])
    stop_fraction = float(config["execution"]["stop_fraction"])
    stop_price = entry * (1 - side * stop_fraction)
    economics = config["economics"]
    notional = float(economics["notional_usdc"])
    venue_leverage = float(economics["selected_venue_leverage"])
    max_leverage = float(economics["venue_max_leverage"])
    collateral = notional / venue_leverage
    loss_capacity = collateral * (1 - venue_leverage / max_leverage * .25)
    opening_fee = notional * float(economics["roundtrip_bps"][scenario]) / 10_000
    opening_fee += float(economics["oracle_net_cost_usdc_per_trade"])
    annual_carry = float(economics["annual_rollover_cost_pct"][scenario][
        "long" if side == 1 else "short"]) / 100
    exit_price = float(frame.loc[exit_time, "open"])
    exit_reason = "state"
    liquidated = False
    max_adverse = 0.0
    elapsed_days = 0.0
    for stamp, row in path.iterrows():
        elapsed_days = (stamp - entry_time).total_seconds() / 86400
        carry_cost = notional * annual_carry * elapsed_days / 365.25
        remaining_price_loss = loss_capacity - opening_fee - carry_cost
        liquidation_fraction = remaining_price_loss / notional
        if liquidation_fraction <= 0:
            exit_price, exit_reason, liquidated = float(row.open), "carry_liquidation", True
            break
        adverse_open = max(0.0, side * (entry - float(row.open)) / entry)
        adverse_bar = max(0.0, ((entry - float(row.low)) / entry if side == 1
                                else (float(row.high) - entry) / entry))
        max_adverse = max(max_adverse, adverse_bar)
        if adverse_open >= liquidation_fraction:
            exit_price, exit_reason, liquidated = float(row.open), "gap_liquidation", True
            break
        gap_stop = float(row.open) <= stop_price if side == 1 else float(row.open) >= stop_price
        if gap_stop:
            exit_price, exit_reason = float(row.open), "gap_stop"
            break
        if liquidation_fraction <= stop_fraction and adverse_bar >= liquidation_fraction:
            exit_price = entry * (1 - side * liquidation_fraction)
            exit_reason, liquidated = "intrabar_liquidation", True
            break
        hit_stop = float(row.low) <= stop_price if side == 1 else float(row.high) >= stop_price
        if hit_stop:
            exit_price, exit_reason = stop_price, "stop"
            break
    actual_exit_time = stamp if exit_reason != "state" else exit_time
    elapsed_days = (actual_exit_time - entry_time).total_seconds() / 86400
    carry_cost = notional * annual_carry * elapsed_days / 365.25
    gross_return = side * (exit_price / entry - 1)
    net_pnl = (-collateral if liquidated else
               notional * gross_return - opening_fee - carry_cost)
    return {"entry_time": entry_time.isoformat(), "exit_time": actual_exit_time.isoformat(),
            "side": side, "weeks_planned": episode["weeks"], "elapsed_days": elapsed_days,
            "entry": entry, "exit": exit_price, "gross_return": gross_return,
            "gross_pnl_usdc": notional * gross_return,
            "max_adverse_fraction": max_adverse, "exit_reason": exit_reason,
            "liquidated": liquidated, "carry_cost_usdc": carry_cost,
            "variable_and_oracle_cost_usdc": opening_fee, "net_pnl_usdc": net_pnl}


def metrics(rows: list[dict[str, Any]], capital: float) -> dict[str, Any]:
    if not rows:
        return {"trades": 0, "profit_factor": 0, "expectancy_usdc": -99,
                "net_pnl_usdc": 0, "max_drawdown_pct": 100,
                "positive_year_ratio": 0, "liquidation_count": 0}
    pnl = pd.Series([row["net_pnl_usdc"] for row in rows], dtype=float)
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = capital + pnl.cumsum()
    peak = pd.concat([pd.Series([capital]), equity]).cummax().iloc[1:].reset_index(drop=True)
    drawdown = (1 - equity.reset_index(drop=True) / peak).max()
    years: dict[int, float] = {}
    for row in rows:
        year = pd.Timestamp(row["entry_time"]).year
        years[year] = years.get(year, 0) + row["net_pnl_usdc"]
    return {"trades": len(rows), "profit_factor": float(gains / losses) if losses else 99.0,
            "expectancy_usdc": float(pnl.mean()), "net_pnl_usdc": float(pnl.sum()),
            "gross_pnl_usdc": sum(row["gross_pnl_usdc"] for row in rows),
            "gross_expectancy_usdc": sum(row["gross_pnl_usdc"] for row in rows) / len(rows),
            "execution_and_oracle_cost_usdc": sum(
                row["variable_and_oracle_cost_usdc"] for row in rows),
            "carry_cost_usdc": sum(row["carry_cost_usdc"] for row in rows),
            "max_drawdown_pct": float(max(0, drawdown) * 100),
            "positive_year_ratio": sum(value > 0 for value in years.values()) / len(years),
            "positive_years": sum(value > 0 for value in years.values()),
            "observed_years": len(years),
            "liquidation_count": sum(bool(row["liquidated"]) for row in rows),
            "stop_count": sum("stop" in row["exit_reason"] for row in rows),
            "long_trades": sum(row["side"] == 1 for row in rows),
            "short_trades": sum(row["side"] == -1 for row in rows),
            "long_net_pnl_usdc": sum(row["net_pnl_usdc"] for row in rows if row["side"] == 1),
            "short_net_pnl_usdc": sum(row["net_pnl_usdc"] for row in rows if row["side"] == -1),
            "mean_holding_days": sum(row["elapsed_days"] for row in rows) / len(rows)}


def run(frame: pd.DataFrame, config: dict[str, Any], macro_gate: dict[str, Any],
        real_yield: dict[date, float], broad_dollar: dict[date, float],
        files: list[Path]) -> dict[str, Any]:
    assert_train_only(config, macro_gate)
    start, end = map(date.fromisoformat, config["splits"]["train"])
    real_weekly = weekly_latest(real_yield, start, end)
    dollar_weekly = weekly_latest(broad_dollar, start, end)
    common = sorted(set(real_weekly) & set(dollar_weekly))
    macro_rows = [{"friday": stamp, "real_yield": real_weekly[stamp],
                   "broad_dollar": dollar_weekly[stamp]} for stamp in common]
    eligible = {tuple(row["parameter_tuple"]) for row in macro_gate["survivors"]}
    evaluated = []
    train_boundary = pd.Timestamp(end.isoformat(), tz="UTC") + pd.Timedelta(days=1)
    for point in sorted(eligible):
        state_rows = states(macro_rows, *point)
        all_runs = episodes(state_rows)
        runs = []
        censored = 0
        for episode in all_runs:
            exit_time = pd.Timestamp(episode["decision_time_utc"]) + pd.Timedelta(
                weeks=episode["weeks"])
            if exit_time > train_boundary:
                censored += 1
            else:
                runs.append(episode)
        scenarios = {}
        missing = 0
        for scenario in ("base", "conservative", "stress"):
            trades = []
            for episode in runs:
                # episodes() omits flat weeks; planned duration still identifies the first flat/reversal week.
                exit_time = pd.Timestamp(episode["decision_time_utc"]) + pd.Timedelta(
                    weeks=episode["weeks"])
                trade = simulate_episode(frame, episode, exit_time, config, scenario)
                if trade is None:
                    missing += 1
                else:
                    trades.append(trade)
            scenarios[scenario] = metrics(trades, float(config["economics"]["capital_usdc"]))
        gate = config["train_performance_gate"]
        base, conservative, stress = (scenarios[name] for name in ("base", "conservative", "stress"))
        skipped_episodes = missing // 3
        skipped_ratio = skipped_episodes / len(runs) if runs else 1.0
        numeric = (stress["trades"] >= gate["minimum_trades"]
                   and skipped_ratio <= gate["maximum_skipped_episode_ratio"]
                   and base["profit_factor"] >= gate["minimum_base_profit_factor"]
                   and conservative["profit_factor"] >= gate["minimum_conservative_profit_factor"]
                   and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
                   and stress["expectancy_usdc"] >= gate["minimum_stress_expectancy_usdc"]
                   and stress["positive_year_ratio"] >= gate["minimum_stress_positive_year_ratio"]
                   and stress["max_drawdown_pct"] <= gate["maximum_stress_drawdown_pct"]
                   and stress["liquidation_count"] <= gate["maximum_liquidations"])
        evaluated.append({"parameters": {"lookback_weeks": point[0],
                                          "real_yield_change_threshold_bps": point[1],
                                          "broad_dollar_change_threshold_pct": point[2]},
                          "parameter_tuple": list(point), "planned_episodes": len(runs),
                          "censored_after_train_episodes": censored,
                          "missing_episode_scenarios": missing,
                          "skipped_episodes_missing_entry_or_exit": skipped_episodes,
                          "skipped_episode_ratio": skipped_ratio, "scenarios": scenarios,
                          "passes_numeric_train_gate": numeric})
    numeric_passing = {tuple(row["parameter_tuple"]) for row in evaluated
                       if row["passes_numeric_train_gate"]}
    axes = [config["search"][key] for key in ("lookback_weeks",
                                               "real_yield_change_threshold_bps",
                                               "broad_dollar_change_threshold_pct")]
    for row in evaluated:
        row["stable_neighbors"] = adjacent_neighbors(tuple(row["parameter_tuple"]),
                                                       numeric_passing, axes)
        row["passes_train_gate"] = (row["passes_numeric_train_gate"] and
                                     row["stable_neighbors"] >=
                                     config["train_performance_gate"]["minimum_stable_neighbors"])
    survivors = [row for row in evaluated if row["passes_train_gate"]]
    return {"schema_version": 1, "campaign_id": config["campaign_id"],
            "stage": "train_performance", "decision": "PASS_TO_SQ" if survivors else "REJECT_NO_SQ",
            "train_window": [start.isoformat(), end.isoformat()], "attempted": len(evaluated),
            "survivor_count": len(survivors), "survivors": survivors,
            "all_results": evaluated, "m15_bars": len(frame),
            "source_files": [str(path) for path in files],
            "m15_minute_count_distribution": {
                str(int(key)): int(value) for key, value in frame.minute_count.value_counts().sort_index().items()
            },
            "maximum_observed_source_gap_hours": float(
                frame.index.to_series().diff().dt.total_seconds().div(3600).max()),
            "source_fingerprint": hashlib.sha256("".join(
                f"{path}:{path.stat().st_size}:{path.stat().st_mtime_ns}\n" for path in files
            ).encode()).hexdigest(),
            "validation_accessed": False, "oos_accessed": False,
            "holdout_accessed": False, "sqcli_used": False,
            "paper_authorized": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--macro-gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_raw, gate_raw = args.config.read_bytes(), args.macro_gate.read_bytes()
    config, macro_gate = json.loads(config_raw), json.loads(gate_raw)
    start, end = config["splits"]["train"]
    files = train_files(Path(config["xau_source"]["root"]), start, end)
    frame = load_m15(files, start, end)
    source_paths = [Path(config["macro_sources"][key]["path"])
                    for key in ("real_yield", "broad_dollar")]
    result = run(frame, config, macro_gate,
                 load_series(source_paths[0], config["macro_sources"]["real_yield"]["series"]),
                 load_series(source_paths[1], config["macro_sources"]["broad_dollar"]["series"]),
                 files)
    result["config_sha256"] = hashlib.sha256(config_raw).hexdigest()
    result["macro_gate_sha256"] = hashlib.sha256(gate_raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("decision", "m15_bars", "attempted", "survivor_count")}, indent=2))


if __name__ == "__main__":
    main()
