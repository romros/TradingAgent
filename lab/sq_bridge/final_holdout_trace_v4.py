#!/usr/bin/env python3
"""Derive the sole source-bound dynamic-sizing final holdout trace."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from lab.sq_bridge.sq_stop_reconstruction_v4 import reconstruct
from lab.sq_bridge.sq_temporal_trace_v4 import _number, _segments, _timestamp
from lab.sq_bridge.sqcli_supervised_retest import verify_supervised_retest_receipt


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive(*, candidate_id: str, orders_path: Path,
           supervised_holdout_receipt_path: Path,
           temporal_contract_path: Path, small_account_artifact_path: Path,
           cost_model_path: Path, source_timezone: str,
           candles_path: Path, candle_timezone: str,
           candle_contract_path: Path) -> dict:
    receipt = verify_supervised_retest_receipt(
        supervised_holdout_receipt_path, candidate_id=candidate_id,
        orders_path=orders_path, expected_stage="holdout")
    sizing = json.loads(small_account_artifact_path.read_text())
    cost_hash, sizing_hash = _sha(cost_model_path), _sha(small_account_artifact_path)
    if (sizing.get("stage") != "small_account_economics"
            or sizing.get("decision") != "PASS"
            or sizing.get("candidate_ids") != [candidate_id]
            or sizing.get("holdout_accessed") is not False
            or sizing.get("cost_model_sha256") != cost_hash):
        raise ValueError("sizing no autoritza el holdout d'aquest candidat")
    contract = json.loads(temporal_contract_path.read_text())
    holdout_start, holdout_end = _segments(contract)["final_holdout"]
    with orders_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        rows = list(reader)
    required = {"Ticket", "Type", "Open time", "Open price",
                "Close time", "Close price"}
    if required - set(reader.fieldnames or ()) or any(required - set(row) for row in rows):
        raise ValueError("orders.csv holdout sense columnes obligatories")
    source_trades, seen = [], set()
    for row in rows:
        ticket = row["Ticket"].strip()
        if not ticket or ticket in seen:
            raise ValueError("ticket SQ holdout buit o duplicat")
        seen.add(ticket)
        opened_utc, opened_day = _timestamp(row["Open time"], source_timezone)
        closed_utc, closed_day = _timestamp(row["Close time"], source_timezone)
        if (closed_utc <= opened_utc or opened_day < holdout_start
                or closed_day > holdout_end):
            raise ValueError("trade SQ fora o creuant el holdout segellat")
        direction = row["Type"].strip().lower()
        if direction not in {"buy", "sell", "long", "short"}:
            raise ValueError("direccio SQ holdout desconeguda")
        side = "long" if direction in {"buy", "long"} else "short"
        entry = _number(row["Open price"], "preu d'entrada")
        exit_price = _number(row["Close price"], "preu de sortida")
        if not all(math.isfinite(value) and value > 0 for value in (entry, exit_price)):
            raise ValueError("preu SQ holdout invalid")
        sign = 1 if side == "long" else -1
        source_trades.append({
            "trade_id": f"{candidate_id}:{ticket}",
            "entry_timestamp": opened_utc.isoformat(), "entry_price": entry,
            "gross_return_pct": sign * (exit_price - entry) / entry * 100,
            "side": side,
            "holding_days": (closed_utc - opened_utc).total_seconds() / 86400,
        })
    sqx = Path(receipt["retest_output_sqx_path"])
    trades, stop_evidence = reconstruct(
        candidate_id=candidate_id, source_trades=source_trades, sqx_path=sqx,
        candles_path=candles_path, candle_timezone=candle_timezone,
        candle_contract_path=candle_contract_path)
    return {
        "schema_version": 2, "trace_type": "final_holdout_trade_trace",
        "source": "single_supervised_uncensored_sq_holdout",
        "candidate_id": candidate_id, "capital_usdc": 200,
        "selection_frozen_before_holdout": True,
        "parameters_changed_after_holdout": False,
        "holdout_evaluation_count": 1,
        "position_notional_usdc": sizing["position_notional_usdc"],
        "risk_per_trade_pct": sizing["risk_per_trade_pct"],
        "selected_leverage": sizing["selected_leverage"],
        "cost_model_sha256": cost_hash,
        "small_account_artifact_sha256": sizing_hash,
        "trades": trades,
        "orders_path": str(orders_path.resolve()), "orders_sha256": _sha(orders_path),
        "supervised_holdout_receipt_path": str(supervised_holdout_receipt_path.resolve()),
        "supervised_holdout_receipt_sha256": _sha(supervised_holdout_receipt_path),
        "temporal_contract_path": str(temporal_contract_path.resolve()),
        "temporal_contract_sha256": _sha(temporal_contract_path),
        "small_account_artifact_path": str(small_account_artifact_path.resolve()),
        "cost_model_path": str(cost_model_path.resolve()),
        "source_timezone": source_timezone,
        **stop_evidence,
    }


def rebuild_from_trace(trace: dict) -> dict:
    for path_key, hash_key in (
            ("orders_path", "orders_sha256"),
            ("supervised_holdout_receipt_path", "supervised_holdout_receipt_sha256"),
            ("temporal_contract_path", "temporal_contract_sha256"),
            ("small_account_artifact_path", "small_account_artifact_sha256"),
            ("cost_model_path", "cost_model_sha256"),
            ("source_sqx_path", "source_sqx_sha256"),
            ("candles_path", "candles_sha256"),
            ("candle_contract_path", "candle_contract_sha256")):
        path = Path(trace.get(path_key, ""))
        if not path.is_file() or _sha(path) != trace.get(hash_key):
            raise ValueError("font del holdout manipulada")
    return derive(
        candidate_id=trace.get("candidate_id", ""),
        orders_path=Path(trace["orders_path"]),
        supervised_holdout_receipt_path=Path(trace["supervised_holdout_receipt_path"]),
        temporal_contract_path=Path(trace["temporal_contract_path"]),
        small_account_artifact_path=Path(trace["small_account_artifact_path"]),
        cost_model_path=Path(trace["cost_model_path"]),
        source_timezone=trace.get("source_timezone", ""),
        candles_path=Path(trace["candles_path"]),
        candle_timezone=trace.get("candle_timezone", ""),
        candle_contract_path=Path(trace["candle_contract_path"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--supervised-holdout-receipt", required=True, type=Path)
    parser.add_argument("--temporal-contract", required=True, type=Path)
    parser.add_argument("--small-account-artifact", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--candles", required=True, type=Path)
    parser.add_argument("--candle-timezone", required=True)
    parser.add_argument("--candle-contract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = derive(
        candidate_id=args.candidate_id, orders_path=args.orders,
        supervised_holdout_receipt_path=args.supervised_holdout_receipt,
        temporal_contract_path=args.temporal_contract,
        small_account_artifact_path=args.small_account_artifact,
        cost_model_path=args.cost_model, source_timezone=args.source_timezone,
        candles_path=args.candles, candle_timezone=args.candle_timezone,
        candle_contract_path=args.candle_contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"candidate_id": args.candidate_id,
                      "holdout_trades": len(result["trades"])}, indent=2))


if __name__ == "__main__":
    main()
