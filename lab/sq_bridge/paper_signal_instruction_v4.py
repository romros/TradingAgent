#!/usr/bin/env python3
"""Build an inert paper signal instruction directly from verified IR and candles."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from lab.sq_bridge.paper_order_sizing_v4 import size_entry
from lab.sq_bridge.paper_package_artifact_v4 import verify_package
from lab.sq_bridge.sqx_to_ir import validate_executable_ir
from lab.sq_bridge.strategy_ir_runtime import evaluate_entries, sq_atr


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stop_pct(plan: dict, frame: pd.DataFrame) -> float:
    spec = plan["stop_loss"]
    entry = float(frame.iloc[-1]["open"])
    if spec["type"] == "percent":
        result = float(spec["percent"])
    elif spec["type"] == "atr":
        if len(frame) < 2:
            raise ValueError("historia insuficient per stop ATR paper")
        atr = round(float(sq_atr(frame, int(spec["period"])).iloc[-2]), 6)
        result = float(spec["multiple"]) * atr / entry * 100
    else:
        raise ValueError("stop paper no executable")
    if not math.isfinite(result) or result <= 0:
        raise ValueError("distancia de stop paper invalida")
    return result


def build_instruction(*, config_path: Path, frame: pd.DataFrame,
                      equity_usdc: float) -> dict:
    """Evaluate the latest bar and size it; never contact Ostium or a signer."""
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text())
    if not verify_package(config, config_path):
        raise ValueError("paquet paper Alquimia invalid")
    if (not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None
            or not frame.index.is_unique or not frame.index.is_monotonic_increasing
            or any(timestamp.utcoffset().total_seconds() != 0
                   for timestamp in frame.index)):
        raise ValueError("candles paper han de ser UTC, uniques i ordenades")
    required = {"open", "high", "low", "close"}
    if (not required <= set(frame.columns) or frame.empty
            or frame[list(required)].isna().any().any()
            or (frame[list(required)] <= 0).any().any()
            or (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any()
            or (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any()):
        raise ValueError("OHLC paper invalid")
    ir_path = (config_path.parent / config["strategy_ir_path"]).resolve()
    if not ir_path.is_file() or _sha(ir_path) != config["strategy_ir_sha256"]:
        raise ValueError("IR paper absent o manipulat")
    ir = json.loads(ir_path.read_text())
    validate_executable_ir(ir, require_stop_loss=True)
    entries = evaluate_entries(ir, frame)
    active = [side for side in ("long", "short")
              if entries[side] is not None and bool(entries[side].iloc[-1])]
    timestamp = frame.index[-1]
    execution = ir["execution"]
    if execution.get("dont_trade_on_weekends") is True:
        hhmm = timestamp.hour * 100 + timestamp.minute
        blocked = (timestamp.dayofweek == 5
                   or timestamp.dayofweek == 4
                      and hhmm >= int(execution.get("weekend_friday_close_hhmm", 1700))
                   or timestamp.dayofweek == 6
                      and hhmm < int(execution.get("weekend_sunday_open_hhmm", 1700)))
        if blocked:
            active = []
    if not active:
        return {
            "schema_version": 1, "decision": "NO_PAPER_SIGNAL",
            "order_sent": False, "candidate_id": config["candidate_id"],
            "signal_timestamp": timestamp.isoformat(),
        }
    if len(active) != 1:
        raise ValueError("senyals paper long i short simultanis")
    side = active[0]
    plan = ir["trade_plans"].get(side)
    if not isinstance(plan, dict) or int(plan.get("exit_after_bars", 0)) <= 0:
        raise ValueError("paper requereix una sortida temporal acotada")
    timeframe = (ir.get("market") or {}).get("timeframe")
    if timeframe != "D1":
        raise ValueError("contracte de holding paper implementat nomes per D1")
    exit_bars = int(plan["exit_after_bars"])
    # Convert trading bars to calendar days and reserve a full extra week for
    # holiday clusters. This is intentionally more conservative than the
    # observed maximum used during sizing.
    holding_days = max(
        float(config["maximum_holding_days"]), math.ceil(exit_bars * 7 / 5) + 7)
    stop_pct = _stop_pct(plan, frame)
    sizing = size_entry(
        config_path=config_path, equity_usdc=equity_usdc,
        initial_stop_distance_pct=stop_pct, side=side,
        maximum_holding_days=holding_days)
    entry = float(frame.iloc[-1]["open"])
    stop = entry * (1 - stop_pct / 100 if side == "long"
                    else 1 + stop_pct / 100)
    return {
        **sizing, "decision": "PASS_PAPER_SIGNAL_INSTRUCTION",
        "strategy_ir_sha256": config["strategy_ir_sha256"],
        "signal_timestamp": timestamp.isoformat(),
        "entry_price": entry, "stop_price": stop,
        "exit_after_bars": exit_bars,
        "maximum_holding_days_for_cost_buffer": holding_days,
    }
