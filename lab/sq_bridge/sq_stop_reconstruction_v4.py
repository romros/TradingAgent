"""Reconstruct exact initial SQ stops for observed trades from frozen candles."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from lab.sq_bridge.candle_data_v4 import load_candles
from lab.sq_bridge.candle_source_contract_v4 import verify as verify_candles
from lab.sq_bridge.sqx_extract import extract as extract_sqx
from lab.sq_bridge.sqx_to_ir import canonical_ir, validate_executable_ir
from lab.sq_bridge.strategy_ir_runtime import sq_atr


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconstruct(*, candidate_id: str, source_trades: list[dict],
                sqx_path: Path, candles_path: Path, candle_timezone: str,
                candle_contract_path: Path) -> tuple[list[dict], dict]:
    contract = extract_sqx(sqx_path)
    ir = canonical_ir(contract)
    validate_executable_ir(ir, require_stop_loss=True)
    if ir.get("strategy_id") != candidate_id:
        raise ValueError("SQX de stops no coincideix amb candidat")
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
        raise ValueError("contracte SQ-Dukascopy no autoritza candles de stops")
    frame = load_candles(candles_path, candle_timezone)
    periods = sorted({plan["stop_loss"]["period"]
                      for plan in ir["trade_plans"].values()
                      if plan is not None and plan["stop_loss"]["type"] == "atr"})
    atrs = {period: sq_atr(frame, period) for period in periods}
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
            raise ValueError("stop SQ no executable")
        trades.append({
            **{key: trade[key] for key in (
                "trade_id", "entry_timestamp", "gross_return_pct",
                "side", "holding_days")},
            "initial_stop_distance_pct": stop_pct,
        })
    trades.sort(key=lambda row: row["trade_id"])
    return trades, {
        "source_sqx_path": str(sqx_path.resolve()),
        "source_sqx_sha256": _sha(sqx_path),
        "source_strategy_xml_sha256": contract["strategy_xml_sha256"],
        "candles_path": str(candles_path.resolve()),
        "candles_sha256": _sha(candles_path),
        "candle_contract_path": str(candle_contract_path.resolve()),
        "candle_contract_sha256": _sha(candle_contract_path),
        "candle_timezone": candle_timezone,
        "stop_distance_semantics": "SQ_initial_ATR_previous_bar_or_fixed_percent",
    }
