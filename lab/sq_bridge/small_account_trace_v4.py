#!/usr/bin/env python3
"""Derive per-trade initial SQ stop distances for canonical 200-USDC sizing."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from lab.sq_bridge.sq_temporal_trace_v4 import rebuild_from_trace as rebuild_temporal
from lab.sq_bridge.sq_stop_reconstruction_v4 import reconstruct


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive(*, candidate_id: str, temporal_trace_path: Path,
           candles_path: Path, candle_timezone: str,
           candle_contract_path: Path,
           cost_model_path: Path, venue_max_leverage: float,
           risk_per_trade_pct: float = 1.5) -> dict:
    if (not isinstance(venue_max_leverage, (int, float))
            or isinstance(venue_max_leverage, bool)
            or not math.isfinite(venue_max_leverage) or venue_max_leverage <= 0
            or not isinstance(risk_per_trade_pct, (int, float))
            or isinstance(risk_per_trade_pct, bool)
            or not math.isfinite(risk_per_trade_pct) or risk_per_trade_pct <= 0):
        raise ValueError("risc o leverage de sizing invalid")
    temporal_raw = json.loads(temporal_trace_path.read_text())
    temporal = rebuild_temporal(temporal_raw)
    if temporal != temporal_raw or temporal.get("candidate_id") != candidate_id:
        raise ValueError("trace temporal no reproduible per sizing")
    if temporal.get("source_timezone") != candle_timezone:
        raise ValueError("timezone de candles no coincideix amb SQ orders")
    receipt = json.loads(
        Path(temporal["supervised_retest_receipt_path"]).read_text())
    sqx = Path(receipt["retest_output_sqx_path"])
    source_trades = [*temporal["train_trades"],
                     *(trade for window in temporal["oos_windows"]
                       for trade in window["trades"])]
    trades, stop_evidence = reconstruct(
        candidate_id=candidate_id, source_trades=source_trades, sqx_path=sqx,
        candles_path=candles_path, candle_timezone=candle_timezone,
        candle_contract_path=candle_contract_path)
    return {
        "schema_version": 2,
        "trace_type": "small_account_trade_trace",
        "source": "reconstructed_sq_initial_stop_from_frozen_candles",
        "candidate_id": candidate_id,
        "capital_usdc": 200,
        "holdout_accessed": False,
        "stop_loss_required": True,
        "risk_per_trade_pct": risk_per_trade_pct,
        "venue_max_leverage": venue_max_leverage,
        "cost_model_sha256": _sha(cost_model_path),
        "trades": trades,
        "temporal_trace_path": str(temporal_trace_path.resolve()),
        "temporal_trace_sha256": _sha(temporal_trace_path),
        **stop_evidence,
        "cost_model_path": str(cost_model_path.resolve()),
    }


def rebuild_from_trace(trace: dict) -> dict:
    for path_key, hash_key in (
            ("temporal_trace_path", "temporal_trace_sha256"),
            ("source_sqx_path", "source_sqx_sha256"),
            ("candles_path", "candles_sha256"),
            ("candle_contract_path", "candle_contract_sha256"),
            ("cost_model_path", "cost_model_sha256")):
        path = Path(trace.get(path_key, ""))
        if not path.is_file() or _sha(path) != trace.get(hash_key):
            raise ValueError("font de sizing manipulada")
    result = derive(
        candidate_id=trace.get("candidate_id", ""),
        temporal_trace_path=Path(trace["temporal_trace_path"]),
        candles_path=Path(trace["candles_path"]),
        candle_timezone=trace.get("candle_timezone", ""),
        candle_contract_path=Path(trace["candle_contract_path"]),
        cost_model_path=Path(trace["cost_model_path"]),
        venue_max_leverage=trace.get("venue_max_leverage"),
        risk_per_trade_pct=trace.get("risk_per_trade_pct"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--temporal-trace", required=True, type=Path)
    parser.add_argument("--candles", required=True, type=Path)
    parser.add_argument("--candle-timezone", required=True)
    parser.add_argument("--candle-contract", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--risk-per-trade-pct", type=float, default=1.5)
    parser.add_argument("--venue-max-leverage", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = derive(
        candidate_id=args.candidate_id,
        temporal_trace_path=args.temporal_trace,
        candles_path=args.candles, candle_timezone=args.candle_timezone,
        candle_contract_path=args.candle_contract,
        cost_model_path=args.cost_model,
        venue_max_leverage=args.venue_max_leverage,
        risk_per_trade_pct=args.risk_per_trade_pct)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"candidate_id": args.candidate_id,
                      "trades": len(result["trades"]),
                      "maximum_initial_stop_distance_pct": max(
                          row["initial_stop_distance_pct"] for row in result["trades"])},
                     indent=2))


if __name__ == "__main__":
    main()
