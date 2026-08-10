#!/usr/bin/env python3
"""CFTC-only frequency preflight for the preregistered Gold flow family v34."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from lab.sq_bridge.xauusd_cftc_flow_preflight_v32 import DATE_FIELDS, _clean, _report_date


def parameter_grid(config: dict[str, Any]) -> list[tuple[int, float, int]]:
    search = config["search"]
    points = list(itertools.product(search["lookback_weeks"],
                                    search["net_change_threshold_open_interest_pct_points"],
                                    search["hold_weeks"]))
    if len(points) != search["attempt_budget"]:
        raise ValueError("attempt budget does not match frozen grid")
    return points


def load_positions(paths: list[Path], expected: dict[str, str]) -> dict[date, float]:
    result: dict[date, float] = {}
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            members = [name for name in archive.namelist() if not name.endswith("/")]
            if len(members) != 1:
                raise ValueError(f"{path}: expected one member")
            with archive.open(members[0]) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                fields = reader.fieldnames or []
                candidates = [field for field in DATE_FIELDS if field in fields]
                if len(candidates) != 1:
                    raise ValueError(f"{path}: ambiguous date field")
                for row in reader:
                    if _clean(row.get("CFTC_Contract_Market_Code")) != expected["cftc_contract_market_code"]:
                        continue
                    identity = (_clean(row.get("Market_and_Exchange_Names")),
                                _clean(row.get("CFTC_Commodity_Code")))
                    if identity != (expected["market_and_exchange_name"], expected["cftc_commodity_code"]):
                        raise ValueError(f"{path}: identity mismatch")
                    stamp = _report_date(row, candidates[0])
                    if stamp in result:
                        raise ValueError(f"duplicate report date: {stamp}")
                    oi = int(_clean(row["Open_Interest_All"]).replace(",", ""))
                    long = int(_clean(row["M_Money_Positions_Long_All"]).replace(",", ""))
                    short = int(_clean(row["M_Money_Positions_Short_All"]).replace(",", ""))
                    if oi <= 0 or min(long, short) < 0:
                        raise ValueError(f"invalid positions on {stamp}")
                    result[stamp] = (long - short) / oi * 100
    return result


def available_rows(ledger: dict[str, Any], positions: dict[date, float],
                   start: date, end: date) -> list[dict[str, Any]]:
    rows = []
    for item in ledger["ledger"]:
        stamp = date.fromisoformat(item["report_date"])
        if not start <= stamp <= end:
            continue
        if stamp not in positions:
            raise ValueError(f"ledger report absent from positions: {stamp}")
        rows.append({"report_date": stamp, "available_at": item["available_at"],
                     "available": item["status"] == "AVAILABLE_CONSERVATIVE",
                     "net_oi_pct": positions[stamp]})
    return rows


def raw_signals(rows: list[dict[str, Any]], lookback: int, threshold: float) -> list[dict[str, Any]]:
    output = []
    for index in range(lookback, len(rows)):
        window = rows[index - lookback:index + 1]
        current, prior = window[-1], window[0]
        expected_days = lookback * 7
        actual_days = (current["report_date"] - prior["report_date"]).days
        if not all(row["available"] for row in window) or abs(actual_days - expected_days) > 2:
            continue
        change = current["net_oi_pct"] - prior["net_oi_pct"]
        side = 1 if change >= threshold else -1 if change <= -threshold else 0
        if side:
            output.append({"report_date": current["report_date"],
                           "available_at": current["available_at"], "side": side,
                           "net_change_oi_pct_points": change})
    return output


def non_overlapping(signals: list[dict[str, Any]], hold_weeks: int) -> list[dict[str, Any]]:
    trades, next_free = [], None
    for signal in signals:
        entry = datetime.fromisoformat(signal["available_at"])
        if next_free is not None and entry < next_free:
            continue
        exit_at = entry + timedelta(weeks=hold_weeks)
        trades.append({**signal, "entry_at": entry.isoformat(), "exit_at": exit_at.isoformat(),
                       "hold_weeks": hold_weeks})
        next_free = exit_at
    return trades


def adjacent_neighbors(point: tuple[int, float, int], passing: set[tuple], axes: list[list]) -> int:
    count = 0
    for index, axis in enumerate(axes):
        position = axis.index(point[index])
        for neighbor in (position - 1, position + 1):
            if 0 <= neighbor < len(axis):
                candidate = list(point)
                candidate[index] = axis[neighbor]
                count += tuple(candidate) in passing
    return count


def evaluate(config: dict[str, Any], ledger: dict[str, Any], positions: dict[date, float]) -> dict[str, Any]:
    forbidden = ("xau_performance_accessed", "validation_accessed", "oos_accessed",
                 "holdout_accessed", "sqcli_authorized", "paper_authorized", "live_authorized")
    if any(config.get(field) is not False for field in forbidden):
        raise ValueError("frequency preflight requires all performance and trading access sealed")
    if ledger.get("decision") != "PASS_CONSERVATIVE_LEDGER":
        raise ValueError("availability ledger has not passed")
    start, end = map(date.fromisoformat, config["splits"]["train"])
    rows = available_rows(ledger, positions, start, end)
    evaluated = []
    gate = config["frequency_gate"]
    for point in parameter_grid(config):
        trades = non_overlapping(raw_signals(rows, point[0], point[1]), point[2])
        sides = Counter(row["side"] for row in trades)
        years = {side: len({row["report_date"].year for row in trades if row["side"] == side})
                 for side in (1, -1)}
        exposed = sum(point[2] for _ in trades) / len(rows) if rows else 1
        numeric = (len(trades) >= gate["minimum_trades"]
                   and all(sides[side] >= gate["minimum_trades_per_side"] for side in (1, -1))
                   and all(years[side] >= gate["minimum_entry_years_per_side"] for side in (1, -1))
                   and exposed <= gate["maximum_exposed_week_ratio"])
        evaluated.append({"parameter_tuple": list(point),
                          "parameters": {"lookback_weeks": point[0],
                                         "threshold_oi_pct_points": point[1],
                                         "hold_weeks": point[2]},
                          "trades": len(trades), "long_trades": sides[1],
                          "short_trades": sides[-1], "long_entry_years": years[1],
                          "short_entry_years": years[-1], "exposed_week_ratio": exposed,
                          "passes_numeric_frequency_gate": numeric})
    numeric = {tuple(row["parameter_tuple"]) for row in evaluated
               if row["passes_numeric_frequency_gate"]}
    axes = [config["search"][key] for key in
            ("lookback_weeks", "net_change_threshold_open_interest_pct_points", "hold_weeks")]
    for row in evaluated:
        row["stable_neighbors"] = adjacent_neighbors(tuple(row["parameter_tuple"]), numeric, axes)
        row["passes_frequency_gate"] = (row["passes_numeric_frequency_gate"] and
                                         row["stable_neighbors"] >= gate["minimum_stable_neighbors"])
    survivors = [row for row in evaluated if row["passes_frequency_gate"]]
    survivor_points = {tuple(row["parameter_tuple"]) for row in survivors}
    performance_points = []
    for row in evaluated:
        point = tuple(row["parameter_tuple"])
        adjacent_to_survivor = any(adjacent_neighbors(survivor, {point}, axes) > 0
                                   for survivor in survivor_points)
        if row["passes_numeric_frequency_gate"] and (point in survivor_points or adjacent_to_survivor):
            performance_points.append(row["parameter_tuple"])
    return {"schema_version": 1, "campaign_id": config["campaign_id"],
            "stage": "positioning_frequency_preflight",
            "decision": "PASS_TO_TRAIN_PERFORMANCE" if survivors else "REJECT_POSITIONING_FREQUENCY",
            "train_window": [start.isoformat(), end.isoformat()], "train_report_rows": len(rows),
            "available_train_rows": sum(row["available"] for row in rows),
            "excluded_train_rows": sum(not row["available"] for row in rows),
            "attempted": len(evaluated), "survivor_count": len(survivors),
            "survivors": survivors, "performance_points": performance_points,
            "performance_points_policy": config["search"]["performance_points_policy"],
            "all_results": evaluated,
            "xau_performance_accessed": False, "validation_accessed": False,
            "oos_accessed": False, "holdout_accessed": False, "sqcli_used": False,
            "paper_authorized": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.config.read_bytes()
    config = json.loads(raw)
    ledger_path = Path(config["availability_ledger"])
    ledger_raw = ledger_path.read_bytes()
    paths = sorted(Path().glob(config["position_source_glob"]))
    result = evaluate(config, json.loads(ledger_raw), load_positions(paths, config["expected_identity"]))
    result["config_sha256"] = hashlib.sha256(raw).hexdigest()
    result["ledger_sha256"] = hashlib.sha256(ledger_raw).hexdigest()
    result["source_archives"] = [str(path) for path in paths]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("decision", "train_report_rows", "available_train_rows", "attempted", "survivor_count")}, indent=2))


if __name__ == "__main__":
    main()
