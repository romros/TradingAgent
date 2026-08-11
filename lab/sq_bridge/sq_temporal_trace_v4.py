#!/usr/bin/env python3
"""Derive a v4 temporal trade trace from one observed SQ orders export."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

from lab.sq_bridge.temporal_split_contract_v4 import digest as contract_digest
from lab.sq_bridge.sqcli_supervised_retest import verify_retest_receipt
from lab.sq_bridge.sqx_extract import extract as extract_sqx


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: str, label: str) -> float:
    try:
        result = float(value.strip().replace(" ", "").replace(",", "."))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{label} SQ temporal no numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} SQ temporal invalid")
    return result


def _timestamp(value: str, timezone: str) -> tuple[datetime, date]:
    try:
        naive = pd.Timestamp(value)
        if naive.tzinfo is not None:
            raise ValueError
        local = naive.tz_localize(timezone, ambiguous="raise", nonexistent="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"timestamp SQ temporal invalid o ambigu: {value!r}") from exc
    return local.tz_convert("UTC").to_pydatetime(), naive.date()


def _utc_boundary(day: date, timezone: str, *, end: bool) -> datetime:
    value = datetime.combine(day, time.max if end else time.min)
    return pd.Timestamp(value).tz_localize(
        timezone, ambiguous="raise", nonexistent="raise").tz_convert("UTC").to_pydatetime()


def _segments(contract: dict) -> dict[str, tuple[date, date]]:
    rows = contract.get("segments")
    if contract.get("contract_type") != "observation_position_temporal_split_v4" \
            or not isinstance(rows, dict):
        raise ValueError("contracte temporal SQ invalid")
    result = {}
    for key in ("train", "validation", "oos", "final_holdout"):
        try:
            start, end = date.fromisoformat(rows[key]["from"]), date.fromisoformat(rows[key]["to"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("segments temporals SQ incomplets") from exc
        if end < start:
            raise ValueError("segment temporal SQ invertit")
        result[key] = (start, end)
    return result


def derive(*, candidate_id: str, orders_path: Path, temporal_contract_path: Path,
           cost_model_path: Path, source_timezone: str,
           retest_receipt_path: Path,
           evaluation_notional_usdc: float = 200) -> dict:
    if not candidate_id or evaluation_notional_usdc != 200:
        raise ValueError("candidat o nocional temporal no canonic")
    contract = json.loads(temporal_contract_path.read_text())
    receipt = verify_retest_receipt(
        retest_receipt_path, candidate_id=candidate_id, orders_path=orders_path)
    sqx_contract = extract_sqx(Path(receipt["retest_output_sqx_path"]))
    point_value = sqx_contract.get("execution", {}).get("point_value")
    order_size_multiplier = sqx_contract.get("execution", {}).get(
        "order_size_multiplier")
    if (not isinstance(point_value, (int, float)) or isinstance(point_value, bool)
            or not math.isfinite(point_value) or point_value <= 0
            or not isinstance(order_size_multiplier, (int, float))
            or isinstance(order_size_multiplier, bool)
            or not math.isfinite(order_size_multiplier)
            or order_size_multiplier <= 0):
        raise ValueError("contracte d'unitats SQ absent al resultat Retest")
    segments = _segments(contract)
    cost_hash = _sha(cost_model_path)
    with orders_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        rows = list(reader)
    required = {"Ticket", "Type", "Open time", "Open price", "Close time",
                "Close price", "Size", "MAE ($)"}
    if required - set(reader.fieldnames or ()) or any(required - set(row) for row in rows):
        raise ValueError("orders.csv temporal sense columnes obligatories")
    buckets: dict[str, list[dict]] = {"train": [], "validation": [], "oos": []}
    seen = set()
    for row in rows:
        ticket = row["Ticket"].strip()
        if not ticket or ticket in seen:
            raise ValueError("ticket SQ temporal buit o duplicat")
        seen.add(ticket)
        opened_utc, opened_day = _timestamp(row["Open time"], source_timezone)
        closed_utc, closed_day = _timestamp(row["Close time"], source_timezone)
        if closed_utc <= opened_utc:
            raise ValueError("trade SQ temporal amb durada no positiva")
        if closed_day >= segments["final_holdout"][0]:
            raise ValueError("orders SQ temporal accedeix al holdout final")
        segment = next((name for name in ("train", "validation", "oos")
                        if segments[name][0] <= closed_day <= segments[name][1]), None)
        if segment is None:
            continue  # embargo between frozen segments
        if opened_day < segments[segment][0]:
            raise ValueError("trade SQ temporal creua una frontera segellada")
        direction = row["Type"].strip().lower()
        if direction not in {"buy", "sell", "long", "short"}:
            raise ValueError("direccio SQ temporal desconeguda")
        side = "long" if direction in {"buy", "long"} else "short"
        entry = _number(row["Open price"], "preu d'entrada")
        exit_price = _number(row["Close price"], "preu de sortida")
        size = _number(row["Size"], "mida")
        mae_usdc = abs(_number(row["MAE ($)"], "MAE"))
        if not all(math.isfinite(value) and value > 0 for value in (entry, exit_price)):
            raise ValueError("preu SQ temporal invalid")
        exposure = entry * size * point_value * order_size_multiplier
        if exposure <= 0:
            raise ValueError("exposicio SQ temporal invalida")
        sign = 1 if side == "long" else -1
        buckets[segment].append({
            "trade_id": f"{candidate_id}:{ticket}",
            "entry_timestamp": opened_utc.isoformat(),
            "entry_price": entry,
            "exit_timestamp": closed_utc.isoformat(),
            "gross_return_pct": sign * (exit_price - entry) / entry * 100,
            "maximum_adverse_excursion_pct": mae_usdc / exposure * 100,
            "side": side,
            "holding_days": (closed_utc - opened_utc).total_seconds() / 86400,
        })
    for values in buckets.values():
        values.sort(key=lambda row: (row["exit_timestamp"], row["trade_id"]))
    windows, counter = [], 0
    for segment in ("validation", "oos"):
        start, end = segments[segment]
        for year in range(start.year, end.year + 1):
            window_start = max(start, date(year, 1, 1))
            window_end = min(end, date(year, 12, 31))
            if window_start > window_end:
                continue
            counter += 1
            trades = [row for row in buckets[segment]
                      if window_start <= pd.Timestamp(row["exit_timestamp"]).tz_convert(
                          source_timezone).date() <= window_end]
            windows.append({
                "window_id": f"w{counter:03d}-{segment}-{year}",
                "start_utc": _utc_boundary(window_start, source_timezone, end=False).isoformat(),
                "end_utc": _utc_boundary(window_end, source_timezone, end=True).isoformat(),
                "trades": trades,
            })
    trace = {
        "schema_version": 1, "trace_type": "temporal_validation_trade_trace",
        "candidate_id": candidate_id, "capital_usdc": 200,
        "evaluation_notional_usdc": 200, "holdout_accessed": False,
        "cost_scenario": "base", "cost_model_sha256": cost_hash,
        "train_end_utc": _utc_boundary(
            segments["train"][1], source_timezone, end=True).isoformat(),
        "train_trades": buckets["train"], "oos_windows": windows,
        "source": "strategyquant_orders_export",
        "orders_path": str(orders_path.resolve()), "orders_sha256": _sha(orders_path),
        "supervised_retest_receipt_path": str(retest_receipt_path.resolve()),
        "supervised_retest_receipt_sha256": _sha(retest_receipt_path),
        "temporal_split_contract_path": str(temporal_contract_path.resolve()),
        "temporal_split_contract_sha256": _sha(temporal_contract_path),
        "temporal_split_contract_digest": contract_digest(contract),
        "cost_model_path": str(cost_model_path.resolve()),
        "source_timezone": source_timezone,
        "source_point_value": point_value,
        "source_order_size_multiplier": order_size_multiplier,
        "mae_semantics": "abs_mae_usdc_over_entry_exposure_from_native_sq_units",
        "return_semantics": "recomputed_from_entry_exit_prices_before_costs",
    }
    return trace


def rebuild_from_trace(trace: dict) -> dict:
    if trace.get("source") != "strategyquant_orders_export":
        raise ValueError("trace temporal no prove d'un export SQ")
    try:
        orders = Path(trace["orders_path"])
        contract = Path(trace["temporal_split_contract_path"])
        costs = Path(trace["cost_model_path"])
        retest_receipt = Path(trace["supervised_retest_receipt_path"])
    except (KeyError, TypeError) as exc:
        raise ValueError("fonts del trace temporal absents") from exc
    for path, key in ((orders, "orders_sha256"),
                      (contract, "temporal_split_contract_sha256")):
        if not path.is_file() or _sha(path) != trace.get(key):
            raise ValueError("font del trace temporal manipulada")
    if not costs.is_file() or _sha(costs) != trace.get("cost_model_sha256"):
        raise ValueError("costos del trace temporal manipulats")
    if (not retest_receipt.is_file()
            or _sha(retest_receipt) != trace.get("supervised_retest_receipt_sha256")):
        raise ValueError("rebut Retest del trace temporal manipulat")
    return derive(
        candidate_id=trace.get("candidate_id", ""), orders_path=orders,
        temporal_contract_path=contract, cost_model_path=costs,
        retest_receipt_path=retest_receipt,
        source_timezone=trace.get("source_timezone", ""),
        evaluation_notional_usdc=trace.get("evaluation_notional_usdc"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--temporal-contract", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--retest-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    trace = derive(
        candidate_id=args.candidate_id, orders_path=args.orders,
        temporal_contract_path=args.temporal_contract,
        cost_model_path=args.cost_model, source_timezone=args.source_timezone,
        retest_receipt_path=args.retest_receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"candidate_id": args.candidate_id,
                      "train_trades": len(trace["train_trades"]),
                      "oos_trades": sum(len(row["trades"]) for row in trace["oos_windows"])},
                     indent=2))


if __name__ == "__main__":
    main()
