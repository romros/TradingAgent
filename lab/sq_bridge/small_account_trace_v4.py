#!/usr/bin/env python3
"""Derive per-trade initial SQ stop distances for canonical 200-USDC sizing."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from lab.sq_bridge.candle_data_v4 import load_candles
from lab.sq_bridge.candle_source_contract_v4 import verify as verify_candles
from lab.sq_bridge.sq_temporal_trace_v4 import rebuild_from_trace as rebuild_temporal
from lab.sq_bridge.sqx_extract import extract as extract_sqx
from lab.sq_bridge.sqx_to_ir import canonical_ir, validate_executable_ir
from lab.sq_bridge.strategy_ir_runtime import sq_atr


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
    contract = extract_sqx(sqx)
    ir = canonical_ir(contract)
    validate_executable_ir(ir, require_stop_loss=True)
    if ir.get("strategy_id") != candidate_id:
        raise ValueError("SQX de sizing no coincideix amb candidat")
    tick_step = ir.get("execution", {}).get("tick_step")
    if (not isinstance(tick_step, (int, float)) or isinstance(tick_step, bool)
            or not math.isfinite(tick_step) or tick_step <= 0):
        raise ValueError("tickStep SQ absent per validar entrada")
    candle_contract_raw = json.loads(candle_contract_path.read_text())
    candle_contract = verify_candles(candle_contract_raw)
    market = ir.get("market", {})
    if (candle_contract != candle_contract_raw
            or candle_contract.get("decision") != "PASS_CANDLE_PARITY"
            or candle_contract.get("performance_accessed") is not False
            or candle_contract.get("sq_candles_sha256") != _sha(candles_path)
            or Path(candle_contract.get("sq_candles_path", "")).resolve()
                != candles_path.resolve()
            or candle_contract.get("sq_timezone") != candle_timezone
            or candle_contract.get("symbol") != market.get("symbol")
            or candle_contract.get("timeframe") != market.get("timeframe")):
        raise ValueError("contracte SQ-Dukascopy no autoritza candles de sizing")
    frame = load_candles(candles_path, candle_timezone)
    periods = sorted({plan["stop_loss"]["period"]
                      for plan in ir["trade_plans"].values()
                      if plan is not None and plan["stop_loss"]["type"] == "atr"})
    atrs = {period: sq_atr(frame, period) for period in periods}
    source_trades = [*temporal["train_trades"],
                     *(trade for window in temporal["oos_windows"]
                       for trade in window["trades"])]
    trades = []
    for trade in source_trades:
        side = trade["side"]
        plan = ir["trade_plans"].get(side)
        if plan is None:
            raise ValueError("trade observat en direccio SQ inactiva")
        timestamp = pd.Timestamp(trade["entry_timestamp"])
        if timestamp.tzinfo is None or timestamp not in frame.index:
            raise ValueError("entrada SQ sense candle exacta")
        location = frame.index.get_loc(timestamp)
        if not isinstance(location, int):
            raise ValueError("entrada SQ amb candle no unica")
        entry = float(trade["entry_price"])
        candle_open = float(frame.iloc[location]["open"])
        if abs(entry - candle_open) > tick_step + 1e-12:
            raise ValueError("preu d'entrada SQ no coincideix amb open de candle")
        stop = plan["stop_loss"]
        if stop["type"] == "percent":
            stop_pct = float(stop["percent"])
        elif stop["type"] == "atr":
            period = stop["period"]
            if location < period:
                raise ValueError("historia insuficient per ATR d'SQ")
            atr = round(float(atrs[period].iloc[location - 1]), 6)
            if not math.isfinite(atr) or atr <= 0:
                raise ValueError("ATR d'SQ invalid al trade")
            stop_pct = float(stop["multiple"]) * atr / entry * 100
        else:
            raise ValueError("stop SQ no executable per sizing")
        trades.append({
            "trade_id": trade["trade_id"],
            "entry_timestamp": trade["entry_timestamp"],
            "gross_return_pct": trade["gross_return_pct"],
            "side": side,
            "holding_days": trade["holding_days"],
            "initial_stop_distance_pct": stop_pct,
        })
    trades.sort(key=lambda row: row["trade_id"])
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
        "source_sqx_path": str(sqx.resolve()),
        "source_sqx_sha256": _sha(sqx),
        "source_strategy_xml_sha256": contract["strategy_xml_sha256"],
        "candles_path": str(candles_path.resolve()),
        "candles_sha256": _sha(candles_path),
        "candle_contract_path": str(candle_contract_path.resolve()),
        "candle_contract_sha256": _sha(candle_contract_path),
        "candle_timezone": candle_timezone,
        "cost_model_path": str(cost_model_path.resolve()),
        "stop_distance_semantics": "SQ_initial_ATR_previous_bar_or_fixed_percent",
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
