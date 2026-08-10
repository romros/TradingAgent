#!/usr/bin/env python3
"""Preflight and train-only falsification for XAUUSD FOMC reaction v29."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


def parameter_grid(config: dict) -> list[tuple]:
    search = config["search"]
    axes = (search["reaction_minutes"], search["mechanism"],
            search["holding_minutes"], search["stop_fraction"])
    points = list(itertools.product(*axes))
    if len(points) != search["attempt_budget"]:
        raise ValueError(
            f'attempt contract mismatch: configured={search["attempt_budget"]}, grid={len(points)}'
        )
    return points


def assert_train_only(config: dict) -> None:
    if any(config.get(flag) is not False for flag in
           ("validation_accessed", "oos_accessed", "holdout_evaluated")):
        raise ValueError("train-only runner requires validation, OOS and holdout to remain sealed")


def train_files(root: Path, start: str, end: str) -> list[Path]:
    base = root / "XAUUSD" / "tf=1m"
    files = []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        files.extend(sorted((base / f"year={year}").glob("month=*/data.parquet")))
    if not files:
        raise FileNotFoundError(f"no XAUUSD train files under {base}")
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
    ).fetchdf()
    frame = frame.rename(columns={"close_price": "close"})
    frame.index = pd.to_datetime(frame.ts, unit="s", utc=True)
    return frame


def event_dates(calendar: dict, start: str, end: str) -> list[pd.Timestamp]:
    return [pd.Timestamp(row["date"]) for row in calendar["events"]
            if start <= row["date"] <= end]


def event_window(frame: pd.DataFrame, event_day: pd.Timestamp, reaction_minutes: int,
                 holding_minutes: int) -> dict | None:
    ny = ZoneInfo("America/New_York")
    release_local = datetime.combine(event_day.date(), time(14, 0), tzinfo=ny)
    release = pd.Timestamp(release_local).tz_convert("UTC")
    entry_time = release + pd.Timedelta(minutes=reaction_minutes)
    exit_time = entry_time + pd.Timedelta(minutes=holding_minutes)
    required = pd.date_range(release, exit_time, freq="15min")
    if any(stamp not in frame.index for stamp in required):
        return None
    selected = frame.loc[required]
    if (selected.minute_count != 15).any():
        return None
    return {"event_date": event_day.date().isoformat(), "release_time": release,
            "entry_time": entry_time, "exit_time": exit_time,
            "reaction_open": float(frame.loc[release, "open"]),
            "entry": float(frame.loc[entry_time, "open"]),
            "exit": float(frame.loc[exit_time, "open"]),
            "path": frame.loc[(frame.index >= entry_time) & (frame.index < exit_time)]}


def simulate_window(window: dict, mechanism: str, stop_fraction: float,
                    venue_leverage: float) -> dict | None:
    reaction = window["entry"] / window["reaction_open"] - 1
    if reaction == 0:
        return None
    direction = 1 if reaction > 0 else -1
    if mechanism == "reversal":
        direction *= -1
    entry = window["entry"]
    stop = entry * (1 - direction * stop_fraction)
    liquidation_distance = 1 / venue_leverage
    exit_price, reason = window["exit"], "time"
    max_adverse = 0.0
    liquidated = False
    for row in window["path"].itertuples():
        adverse_open = max(0.0, direction * (entry - float(row.open)) / entry)
        adverse_bar = max(0.0, ((entry - float(row.low)) / entry if direction == 1
                                else (float(row.high) - entry) / entry))
        max_adverse = max(max_adverse, adverse_bar)
        if adverse_open >= liquidation_distance:
            exit_price, reason, liquidated = float(row.open), "liquidation_gap", True
            break
        gap_stop = float(row.open) <= stop if direction == 1 else float(row.open) >= stop
        hit_stop = float(row.low) <= stop if direction == 1 else float(row.high) >= stop
        if gap_stop or hit_stop:
            exit_price, reason = (float(row.open) if gap_stop else stop), "stop"
            break
    gross = direction * (exit_price / entry - 1)
    return {"date": window["event_date"], "gross_return": gross,
            "reaction_return": reaction, "direction": direction, "stop_fraction": stop_fraction,
            "max_adverse_fraction": max_adverse, "liquidated": liquidated, "exit_reason": reason}


def selected_venue_leverage(stop_fraction: float, economics: dict) -> float:
    safe = math.floor(1 / (stop_fraction * economics["liquidation_buffer_multiple_of_stop"]))
    return float(min(safe, economics["venue_max_leverage"]))


def metrics(trades: pd.DataFrame, cost_bps: float, oracle_cost: float,
            economics: dict) -> dict:
    if trades.empty:
        return {"trades": 0, "profit_factor": 0, "expectancy_usdc": -99,
                "net_pnl_usdc": 0, "max_drawdown_pct": 100, "positive_year_ratio": 0,
                "exposure_multiple": 0, "selected_venue_leverage": 0,
                "margin_pct": 0, "liquidation_count": 0}
    capital = economics["capital_usdc"]
    stop = float(trades.stop_fraction.iloc[0])
    risk = capital * economics["risk_per_trade_pct"] / 100
    notional = risk / stop
    exposure = notional / capital
    venue_leverage = selected_venue_leverage(stop, economics)
    margin_pct = notional / venue_leverage / capital * 100
    pnl = notional * (trades.gross_return - cost_bps / 10_000) - oracle_cost
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = capital + pnl.cumsum()
    drawdown = (1 - equity / equity.cummax()).max()
    years = pd.Series(pnl.to_numpy(), index=pd.to_datetime(trades.date)).groupby(
        lambda stamp: stamp.year).sum()
    return {"trades": int(len(pnl)), "profit_factor": float(gains / losses) if losses else 99.0,
            "expectancy_usdc": float(pnl.mean()), "net_pnl_usdc": float(pnl.sum()),
            "max_drawdown_pct": float(max(0, drawdown) * 100),
            "positive_year_ratio": float((years > 0).mean()),
            "exposure_multiple": float(exposure), "selected_venue_leverage": venue_leverage,
            "margin_pct": float(margin_pct),
            "liquidation_count": int(trades.liquidated.sum())}


def stable_neighbors(point: tuple, passing: set[tuple], axes: list[list]) -> int:
    count = 0
    for index, axis in enumerate(axes):
        position = axis.index(point[index])
        for adjacent in (position - 1, position + 1):
            if 0 <= adjacent < len(axis):
                candidate = list(point)
                candidate[index] = axis[adjacent]
                count += tuple(candidate) in passing
    return count


def preflight(frame: pd.DataFrame, calendar: dict, config: dict, files: list[Path]) -> dict:
    start, end = config["splits"]["train"]
    dates = event_dates(calendar, start, end)
    maximum_reaction = max(config["search"]["reaction_minutes"])
    maximum_hold = max(config["search"]["holding_minutes"])
    complete = [event.date().isoformat() for event in dates
                if event_window(frame, event, maximum_reaction, maximum_hold)]
    incomplete = sorted(set(event.date().isoformat() for event in dates) - set(complete))
    invalid_ohlc = int(((frame.high < frame.low) | (frame.open <= 0) | (frame.close <= 0)).sum())
    minimum_complete = config["train_gate"]["minimum_complete_event_windows"]
    return {"schema_version": 1, "campaign_id": config["campaign_id"], "stage": "data_preflight",
            "decision": "PASS" if len(complete) >= minimum_complete and invalid_ohlc == 0 else "BLOCK",
            "train_event_count": len(dates), "complete_train_event_windows": len(complete),
            "minimum_complete_event_windows": minimum_complete,
            "complete_event_dates": complete, "incomplete_event_dates": incomplete,
            "invalid_ohlc_bars": invalid_ohlc,
            "m15_bars": int(len(frame)), "source_files": [str(path) for path in files],
            "source_fingerprint": hashlib.sha256("".join(
                f"{path}:{path.stat().st_size}:{path.stat().st_mtime_ns}\n" for path in files
            ).encode()).hexdigest(), "performance_accessed": False,
            "validation_accessed": False, "oos_accessed": False,
            "holdout_accessed": False, "live_authorized": False}


def run(frame: pd.DataFrame, calendar: dict, config: dict, files: list[Path]) -> dict:
    assert_train_only(config)
    points = parameter_grid(config)
    start, end = config["splits"]["train"]
    dates = event_dates(calendar, start, end)
    economics, gate = config["economics"], config["train_gate"]
    axes = [config["search"][key] for key in
            ("reaction_minutes", "mechanism", "holding_minutes", "stop_fraction")]
    evaluated = []
    for point in points:
        reaction_minutes, mechanism, holding_minutes, stop = point
        venue_leverage = selected_venue_leverage(stop, economics)
        rows = []
        for event in dates:
            window = event_window(frame, event, reaction_minutes, holding_minutes)
            trade = simulate_window(window, mechanism, stop, venue_leverage) if window else None
            if trade:
                rows.append(trade)
        trades = pd.DataFrame(rows)
        scenarios = {name: metrics(trades, bps, economics["oracle_net_cost_usdc"][name], economics)
                     for name, bps in economics["roundtrip_bps"].items()}
        base, stress = scenarios["base"], scenarios["stress"]
        numeric = (base["trades"] >= gate["minimum_trades"]
                   and base["profit_factor"] >= gate["minimum_base_profit_factor"]
                   and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
                   and stress["expectancy_usdc"] >= gate["minimum_stress_expectancy_usdc"]
                   and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
                   and stress["max_drawdown_pct"] <= gate["maximum_drawdown_pct"]
                   and stress["liquidation_count"] <= gate["maximum_liquidations"]
                   and stress["margin_pct"] <= economics["maximum_margin_pct"])
        evaluated.append({"parameters": {"reaction_minutes": reaction_minutes,
                          "mechanism": mechanism, "holding_minutes": holding_minutes,
                          "stop_fraction": stop}, "parameter_tuple": list(point),
                          "scenarios": scenarios, "passes_numeric_gate": numeric})
    passing = {tuple(row["parameter_tuple"]) for row in evaluated if row["passes_numeric_gate"]}
    for row in evaluated:
        row["stable_neighbors"] = stable_neighbors(tuple(row["parameter_tuple"]), passing, axes)
        row["passes_train_gate"] = (row["passes_numeric_gate"]
                                     and row["stable_neighbors"] >= gate["minimum_stable_neighbors"])
    survivors = [row for row in evaluated if row["passes_train_gate"]]
    return {"schema_version": 1, "campaign_id": config["campaign_id"],
            "stage": "pre_sq_falsification", "decision": "PASS_TO_SQ" if survivors else "REJECT_NO_SQ",
            "train_window": [start, end], "attempted": len(evaluated),
            "survivor_count": len(survivors), "survivors": survivors,
            "all_results": evaluated, "source_files": [str(path) for path in files],
            "validation_accessed": False, "oos_accessed": False,
            "holdout_accessed": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--stage", choices=("preflight", "train"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.config.read_bytes()
    config = json.loads(raw)
    assert_train_only(config)
    parameter_grid(config)
    start, end = config["splits"]["train"]
    files = train_files(Path(config["source_root"]), start, end)
    frame = load_m15(files, start, end)
    calendar = json.loads(Path(config["event_calendar"]).read_text())
    result = preflight(frame, calendar, config, files) if args.stage == "preflight" else run(
        frame, calendar, config, files)
    result["config_sha256"] = hashlib.sha256(raw).hexdigest()
    result["calendar_sha256"] = hashlib.sha256(Path(config["event_calendar"]).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in result if key in
                      {"decision", "train_event_count", "complete_train_event_windows",
                       "attempted", "survivor_count", "performance_accessed"}}, indent=2))


if __name__ == "__main__":
    main()
