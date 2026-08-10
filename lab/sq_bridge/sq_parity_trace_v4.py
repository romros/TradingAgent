#!/usr/bin/env python3
"""Build a canonical StrategyQuant parity trace from observed SQ exports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

import pandas as pd

from lab.sq_bridge.python_parity_trace_v4 import load_mt4_csv
from lab.sq_bridge.parity_artifact_v4 import validate_trace


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if not reader.fieldnames:
            raise ValueError(f"CSV sense capcalera: {path}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"CSV sense files: {path}")
    return rows


def _utc(value: str, source_timezone: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize(
                source_timezone, ambiguous="raise", nonexistent="raise")
        return timestamp.tz_convert("UTC")
    except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError(f"Timestamp SQ invalid o ambigu: {value!r}") from error


def _iso(timestamp: pd.Timestamp) -> str:
    return timestamp.isoformat().replace("+00:00", "Z")


def _direction(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"buy", "long"}:
        return "long"
    if normalized in {"sell", "short"}:
        return "short"
    raise ValueError(f"Direccio SQ desconeguda: {value!r}")


def build(*, candidate_id: str, orders_path: Path, signals_path: Path,
          market_data_path: Path, source_timezone: str, notional_usdc: float,
          output_path: Path) -> dict:
    if not candidate_id.strip():
        raise ValueError("candidate_id buit")
    if (not math.isfinite(notional_usdc) or notional_usdc <= 0
            or isinstance(notional_usdc, bool)):
        raise ValueError("Nocional de paritat invalid")
    candles_frame = load_mt4_csv(market_data_path)
    if not candles_frame.index.is_unique or not candles_frame.index.is_monotonic_increasing:
        raise ValueError("Candles de paritat duplicades o desordenades")
    candle_set = set(candles_frame.index)
    candles = [_iso(value) for value in candles_frame.index]

    signals = []
    for row in _rows(signals_path):
        if set(("Timestamp", "Direction")) - set(row):
            raise ValueError("El log de senyals requereix Timestamp i Direction")
        timestamp = _utc(row["Timestamp"], source_timezone)
        if timestamp not in candle_set:
            raise ValueError("Senyal SQ fora de les candles comunes")
        signals.append({"timestamp": _iso(timestamp),
                        "direction": _direction(row["Direction"])})

    trades = []
    required = {"Type", "Open time", "Open price", "Close time", "Close price"}
    for row in _rows(orders_path):
        if required - set(row):
            raise ValueError(f"orders.csv SQ no conte {sorted(required - set(row))}")
        opened = _utc(row["Open time"], source_timezone)
        closed = _utc(row["Close time"], source_timezone)
        if opened not in candle_set or closed not in candle_set:
            raise ValueError("Trade SQ fora de les candles comunes")
        try:
            entry, exit_price = float(row["Open price"]), float(row["Close price"])
        except (TypeError, ValueError) as error:
            raise ValueError("Preu SQ no numeric") from error
        if not all(math.isfinite(value) and value > 0 for value in (entry, exit_price)):
            raise ValueError("Preu SQ invalid")
        direction = _direction(row["Type"])
        sign = 1 if direction == "long" else -1
        gross_return = sign * (exit_price - entry) / entry
        trades.append({
            "entry_timestamp": _iso(opened), "exit_timestamp": _iso(closed),
            "direction": direction, "entry_price": entry, "exit_price": exit_price,
            "gross_return": gross_return, "pnl": notional_usdc * gross_return,
            "exit_reason": row.get("Close type", "") or "unknown",
        })

    trace = {
        "schema_version": 1, "trace_type": "strategy_parity_trace",
        "source": "strategyquant", "candidate_id": candidate_id,
        "candles": candles, "signals": signals, "trades": trades,
        "notional_usdc": float(notional_usdc), "costs_applied": False,
        "orders_path": str(orders_path.resolve()), "orders_sha256": _sha(orders_path),
        "signals_path": str(signals_path.resolve()), "signals_sha256": _sha(signals_path),
        "market_data_path": str(market_data_path.resolve()),
        "market_data_sha256": _sha(market_data_path),
        "source_timezone": source_timezone,
        "pnl_semantics": "recomputed_from_prices_at_fixed_notional_before_costs",
    }
    validate_trace(trace, "strategyquant")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--market-data", type=Path, required=True)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--notional-usdc", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(
        candidate_id=args.candidate_id, orders_path=args.orders,
        signals_path=args.signals, market_data_path=args.market_data,
        source_timezone=args.source_timezone, notional_usdc=args.notional_usdc,
        output_path=args.output)
    print(json.dumps({"candidate_id": result["candidate_id"],
                      "signals": len(result["signals"]),
                      "trades": len(result["trades"])}, indent=2))


if __name__ == "__main__":
    main()
