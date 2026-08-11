#!/usr/bin/env python3
"""Generate the preregistered train-only US500 D1 hypothesis grid for v4."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.eurusd_d1_hypothesis_trace_v4 import (
    Bar, read_bars, sq_atr_values, true_ranges,
)
from lab.sq_bridge.temporal_split_contract_v4 import (
    build_contract as build_temporal_contract,
    digest as temporal_contract_digest,
)


FAMILIES = (
    ("d1_time_series_momentum", "time_series_momentum", (
        ("central", {"lookback": 126, "hold_bars": 8, "stop_atr": 3.0}),
        ("lookback_105", {"lookback": 105, "hold_bars": 8, "stop_atr": 3.0}),
        ("lookback_147", {"lookback": 147, "hold_bars": 8, "stop_atr": 3.0}),
    )),
    ("d1_shock_reversion", "shock_reversion", (
        ("central", {"shock_atr": 1.5, "hold_bars": 5, "stop_atr": 2.0}),
        ("shock_1_25", {"shock_atr": 1.25, "hold_bars": 5, "stop_atr": 2.0}),
        ("shock_1_75", {"shock_atr": 1.75, "hold_bars": 5, "stop_atr": 2.0}),
    )),
    ("d1_volatility_regime_trend", "volatility_regime_trend", (
        ("central", {"roc_lookback": 20, "roc_threshold_pct": 4.0,
                     "hold_bars": 8, "stop_atr": 3.0}),
        ("threshold_3", {"roc_lookback": 20, "roc_threshold_pct": 3.0,
                         "hold_bars": 8, "stop_atr": 3.0}),
        ("threshold_5", {"roc_lookback": 20, "roc_threshold_pct": 5.0,
                         "hold_bars": 8, "stop_atr": 3.0}),
    )),
)
MARKET_SIDES = ("both", "long", "short")
PRODUCER_ID = "us500_d1_preregistered_hypotheses_v4"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signal(bars: list[Bar], atrs: list[float], index: int,
           family: str, params: dict) -> str | None:
    if index < 20:
        return None
    if family == "time_series_momentum":
        lookback = params["lookback"]
        if index < lookback:
            return None
        change = bars[index].close / bars[index - lookback].close - 1
        return "long" if change > 0 else ("short" if change < 0 else None)
    if family == "shock_reversion":
        move = bars[index].close - bars[index - 1].close
        threshold = params["shock_atr"] * atrs[index]
        return "short" if move >= threshold else ("long" if move <= -threshold else None)
    if family == "volatility_regime_trend":
        lookback = params["roc_lookback"]
        if index < lookback:
            return None
        change_pct = (bars[index].close / bars[index - lookback].close - 1) * 100
        threshold = params["roc_threshold_pct"]
        return "long" if change_pct >= threshold else (
            "short" if change_pct <= -threshold else None)
    raise ValueError(f"unknown US500 hypothesis family: {family}")


def simulate(bars: list[Bar], family: str, params: dict,
             variant_id: str, market_side: str = "both") -> list[dict]:
    if market_side not in MARKET_SIDES:
        raise ValueError(f"unknown market side: {market_side}")
    atrs = sq_atr_values(true_ranges(bars))
    trades, index = [], 20
    while index + 1 + params["hold_bars"] < len(bars):
        side = signal(bars, atrs, index, family, params)
        if side is None or (market_side != "both" and side != market_side):
            index += 1
            continue
        entry_index = index + 1
        atr = round(atrs[index], 6)
        entry = bars[entry_index].open
        stop = (entry - params["stop_atr"] * atr if side == "long"
                else entry + params["stop_atr"] * atr)
        scheduled = entry_index + params["hold_bars"]
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


def build_hypotheses(train: list[Bar]) -> list[dict]:
    result = []
    rationales = {
        "time_series_momentum": "persistent index repricing over an approximately six-month horizon",
        "shock_reversion": "short-horizon normalization after an outsized daily index move",
        "volatility_regime_trend": "directional continuation only after a large absolute 20-session move",
    }
    for base_id, family, definitions in FAMILIES:
        for market_side in MARKET_SIDES:
            hypothesis_id = f"{base_id}_{market_side}"
            central = f"{hypothesis_id}__central"
            variants = []
            for suffix, params in definitions:
                variant_id = f"{hypothesis_id}__{suffix}"
                variants.append({
                    "variant_id": variant_id,
                    "neighbor_of": None if suffix == "central" else central,
                    "family": family, "market_side": market_side,
                    "parameters": params,
                    "trades": simulate(train, family, params, variant_id, market_side),
                })
            result.append({
                "hypothesis_id": hypothesis_id, "base_hypothesis_id": base_id,
                "market_side": market_side, "central_variant_id": central,
                "economic_rationale": rationales[family], "variants": variants,
            })
    return result


def replay_matches(trace: dict) -> bool:
    if trace.get("producer_id") != PRODUCER_ID:
        return False
    source = Path(str(trace.get("source_path", "")))
    train_rows = trace.get("train_rows")
    if not isinstance(train_rows, int) or isinstance(train_rows, bool) or train_rows < 1:
        return False
    try:
        bars = read_bars(source)
    except (OSError, ValueError):
        return False
    return trace.get("hypotheses") == build_hypotheses(bars[:train_rows])


def build(source: Path, cost_model: Path, methodology: Path) -> dict:
    rules, costs = json.loads(methodology.read_text()), json.loads(cost_model.read_text())
    if rules.get("schema_version") != 4:
        raise ValueError("hypothesis producer requires methodology v4")
    if costs.get("decision") != "PASS_COSTS_FROZEN" or costs.get("costs_frozen") is not True:
        raise ValueError("execution costs must be frozen before performance screening")
    bars = read_bars(source)
    temporal_contract = build_temporal_contract(source, methodology)
    train_rows = temporal_contract["segments"]["train"]["last_row_index"] + 1
    hypotheses = build_hypotheses(bars[:train_rows])
    attempted = sum(len(row["variants"]) for row in hypotheses)
    if attempted > rules["hypothesis_screen"]["maximum_attempts"]:
        raise ValueError("preregistered grid exceeds screen attempt budget")
    return {
        "schema_version": 1, "trace_type": "hypothesis_screen_grid_trace",
        "producer_id": PRODUCER_ID, "train_only": True,
        "future_periods_accessed": False, "holdout_accessed": False,
        "cost_model_sha256": _sha(cost_model),
        "screen_notional_usdc": rules["hypothesis_screen"]["screen_notional_usdc"],
        "source_path": str(source.resolve()), "source_sha256": _sha(source),
        "source_rows": len(bars), "train_rows": train_rows,
        "source_first_utc": f"{bars[0].day.isoformat()}T00:00:00+00:00",
        "train_end_utc": f"{bars[train_rows - 1].day.isoformat()}T00:00:00+00:00",
        "temporal_split": rules["temporal_split"],
        "temporal_contract": temporal_contract,
        "temporal_contract_sha256": temporal_contract_digest(temporal_contract),
        "attempted_variants": attempted, "hypotheses": hypotheses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.source, args.cost_model, args.methodology)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"hypotheses": len(result["hypotheses"]),
                      "attempted_variants": result["attempted_variants"]}, indent=2))


if __name__ == "__main__":
    main()
