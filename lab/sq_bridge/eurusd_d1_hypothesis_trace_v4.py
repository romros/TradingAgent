#!/usr/bin/env python3
"""Generate the preregistered train-only EURUSD D1 hypothesis grid for v4."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lab.sq_bridge.temporal_split_contract_v4 import (
    build_contract as build_temporal_contract,
    digest as temporal_contract_digest,
)


@dataclass(frozen=True)
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float


FAMILIES = (
    ("d1_breakout", "breakout", (
        ("central", {"lookback": 55, "hold_bars": 15, "stop_atr": 2.5}),
        ("lookback_45", {"lookback": 45, "hold_bars": 15, "stop_atr": 2.5}),
        ("lookback_65", {"lookback": 65, "hold_bars": 15, "stop_atr": 2.5}),
    )),
    ("d1_momentum", "momentum", (
        ("central", {"lookback": 90, "hold_bars": 20, "stop_atr": 3.0}),
        ("lookback_105", {"lookback": 105, "hold_bars": 20, "stop_atr": 3.0}),
        ("lookback_75", {"lookback": 75, "hold_bars": 20, "stop_atr": 3.0}),
    )),
    ("d1_shock_reversion", "shock_reversion", (
        ("central", {"shock_atr": 1.5, "hold_bars": 5, "stop_atr": 2.0}),
        ("shock_1_25", {"shock_atr": 1.25, "hold_bars": 5, "stop_atr": 2.0}),
        ("shock_1_75", {"shock_atr": 1.75, "hold_bars": 5, "stop_atr": 2.0}),
    )),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_bars(path: Path) -> list[Bar]:
    rows: list[Bar] = []
    with path.open(newline="") as handle:
        for raw in csv.reader(handle):
            if len(raw) != 7:
                raise ValueError("canonical EURUSD row must have seven columns")
            day = date.fromisoformat(raw[0].replace(".", "-"))
            values = [float(value) for value in raw[2:6]]
            if not all(math.isfinite(value) and value > 0 for value in values):
                raise ValueError("non-positive or non-finite EURUSD price")
            open_, high, low, close = values
            if low > min(open_, close) or high < max(open_, close) or low > high:
                raise ValueError("invalid EURUSD OHLC")
            rows.append(Bar(day, open_, high, low, close))
    if len(rows) < 500 or [row.day for row in rows] != sorted({row.day for row in rows}):
        raise ValueError("canonical EURUSD source must be long, unique and ordered")
    return rows


def true_ranges(bars: list[Bar]) -> list[float]:
    result = []
    for index, bar in enumerate(bars):
        previous = bars[index - 1].close if index else bar.open
        result.append(max(bar.high - bar.low, abs(bar.high - previous),
                          abs(bar.low - previous)))
    return result


def atr_at(ranges: list[float], index: int, length: int = 20) -> float | None:
    if index < length:
        return None
    value = sum(ranges[index - length + 1:index + 1]) / length
    return value if value > 0 else None


def signal(bars: list[Bar], ranges: list[float], index: int,
           family: str, params: dict) -> str | None:
    atr = atr_at(ranges, index)
    if atr is None:
        return None
    if family == "breakout":
        lookback = params["lookback"]
        if index < lookback:
            return None
        history = bars[index - lookback:index]
        if bars[index].close > max(row.high for row in history):
            return "long"
        if bars[index].close < min(row.low for row in history):
            return "short"
    elif family == "momentum":
        lookback = params["lookback"]
        if index < lookback:
            return None
        change = bars[index].close / bars[index - lookback].close - 1
        if change > 0:
            return "long"
        if change < 0:
            return "short"
    elif family == "shock_reversion":
        move = bars[index].close - bars[index - 1].close
        if move >= params["shock_atr"] * atr:
            return "short"
        if move <= -params["shock_atr"] * atr:
            return "long"
    else:
        raise ValueError(f"unknown hypothesis family: {family}")
    return None


def simulate(bars: list[Bar], family: str, params: dict,
             variant_id: str) -> list[dict]:
    ranges = true_ranges(bars)
    trades, index = [], 20
    while index < len(bars) - 1:
        side = signal(bars, ranges, index, family, params)
        if side is None:
            index += 1
            continue
        entry_index = index + 1
        atr = atr_at(ranges, index)
        assert atr is not None
        entry = bars[entry_index].open
        stop = (entry - params["stop_atr"] * atr if side == "long"
                else entry + params["stop_atr"] * atr)
        scheduled = min(entry_index + params["hold_bars"], len(bars) - 1)
        exit_index, exit_price, reason = scheduled, bars[scheduled].open, "time"
        for cursor in range(entry_index, scheduled):
            bar = bars[cursor]
            if side == "long" and bar.low <= stop:
                exit_index, exit_price, reason = cursor, min(bar.open, stop), "stop"
                break
            if side == "short" and bar.high >= stop:
                exit_index, exit_price, reason = cursor, max(bar.open, stop), "stop"
                break
        gross = ((exit_price - entry) / entry if side == "long"
                 else (entry - exit_price) / entry) * 100
        trades.append({
            "trade_id": f"{variant_id}-{len(trades):04d}",
            "entry_timestamp": f"{bars[entry_index].day.isoformat()}T00:00:00+00:00",
            "exit_timestamp": f"{bars[exit_index].day.isoformat()}T00:00:00+00:00",
            "gross_return_pct": gross, "side": side,
            "holding_days": (bars[exit_index].day - bars[entry_index].day).days,
            "exit_reason": reason,
        })
        index = max(index + 1, exit_index)
    return trades


def build(source: Path, cost_model: Path, methodology: Path) -> dict:
    rules = json.loads(methodology.read_text())
    if rules.get("schema_version") != 4:
        raise ValueError("hypothesis producer requires methodology v4")
    costs = json.loads(cost_model.read_text())
    if costs.get("decision") != "PASS_COSTS_FROZEN" or costs.get("costs_frozen") is not True:
        raise ValueError("execution costs must be frozen before performance screening")
    bars = read_bars(source)
    temporal_contract = build_temporal_contract(source, methodology)
    train_rows = temporal_contract["segments"]["train"]["last_row_index"] + 1
    train = bars[:train_rows]
    hypotheses = []
    for hypothesis_id, family, definitions in FAMILIES:
        central = f"{hypothesis_id}__central"
        variants = []
        for suffix, params in definitions:
            variant_id = f"{hypothesis_id}__{suffix}"
            variants.append({
                "variant_id": variant_id,
                "neighbor_of": None if suffix == "central" else central,
                "family": family, "parameters": params,
                "trades": simulate(train, family, params, variant_id),
            })
        hypotheses.append({"hypothesis_id": hypothesis_id,
                           "central_variant_id": central,
                           "economic_rationale": {
                               "breakout": "persistent FX repricing after range escape",
                               "momentum": "medium-horizon currency trend persistence",
                               "shock_reversion": "short-horizon liquidity shock normalization",
                           }[family], "variants": variants})
    attempted = sum(len(row["variants"]) for row in hypotheses)
    if attempted > rules["hypothesis_screen"]["maximum_attempts"]:
        raise ValueError("preregistered grid exceeds screen attempt budget")
    return {
        "schema_version": 1, "trace_type": "hypothesis_screen_grid_trace",
        "producer_id": "eurusd_d1_preregistered_hypotheses_v4",
        "train_only": True, "future_periods_accessed": False,
        "holdout_accessed": False,
        "cost_model_sha256": sha256(cost_model),
        "screen_notional_usdc": rules["hypothesis_screen"]["screen_notional_usdc"],
        "source_path": str(source.resolve()), "source_sha256": sha256(source),
        "source_rows": len(bars), "train_rows": train_rows,
        "source_first_utc": f"{bars[0].day.isoformat()}T00:00:00+00:00",
        "train_end_utc": f"{train[-1].day.isoformat()}T00:00:00+00:00",
        "temporal_split": rules["temporal_split"],
        "temporal_contract": temporal_contract,
        "temporal_contract_sha256": temporal_contract_digest(temporal_contract),
        "attempted_variants": attempted, "hypotheses": hypotheses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cost-model", type=Path, required=True)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source, args.cost_model, args.methodology)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"hypotheses": len(result["hypotheses"]),
                      "attempted_variants": result["attempted_variants"],
                      "train_rows": result["train_rows"],
                      "train_end_utc": result["train_end_utc"]}, indent=2))


if __name__ == "__main__":
    main()
