#!/usr/bin/env python3
"""Frozen defensive-equity ATR shock reversal screen."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab.sq_bridge.multi_asset_known_edge_funnel_v1 import load, sma

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "JNJ": ROOT / "data/ibkr_sq_v2/preflight/JNJUSUSD_CANONICAL_D1_2017_2024.csv",
    "KO": ROOT / "data/ibkr_sq_v2/preflight/KOUSUSD_CANONICAL_D1_2017_2024.csv",
    "PEP": ROOT / "data/ibkr_sq_v2/preflight/PEPUSUSD_CANONICAL_D1_2017_2024.csv",
}
PERIODS = {"train": ("2017-01-01", "2021-12-31"), "validation": ("2022-01-01", "2023-12-31"), "oos": ("2024-01-01", "2024-12-31")}


def atr(rows: list[dict], index: int, period: int = 20) -> float | None:
    if index < period:
        return None
    values = []
    for i in range(index - period + 1, index + 1):
        values.append(max(rows[i]["high"] - rows[i]["low"], abs(rows[i]["high"] - rows[i-1]["close"]), abs(rows[i]["low"] - rows[i-1]["close"])))
    return sum(values) / period


def trades(rows: list[dict]) -> list[dict]:
    result = []
    next_free = 0
    for i in range(200, len(rows) - 4):
        if i + 1 < next_free:
            continue
        average, volatility = sma(rows, i, 200), atr(rows, i)
        shock = (rows[i]["close"] / rows[i-1]["close"] - 1) <= -2 * volatility / rows[i-1]["close"]
        if rows[i]["close"] <= average or not shock:
            continue
        entry, exit_ = rows[i+1], rows[i+4]
        buy, sell = entry["open"] * 1.001, exit_["open"] * .999
        shares = math.floor((1000 - 1) / buy)
        if shares:
            result.append({"entry": entry["date"], "exit": exit_["date"], "pnl": shares * (sell - buy) - 2})
            next_free = i + 4
    return result


def metrics(items: list[dict]) -> dict:
    gains = sum(max(x["pnl"], 0) for x in items)
    losses = sum(max(-x["pnl"], 0) for x in items)
    equity = peak = 1000.0
    drawdown = 0.0
    for item in items:
        equity += item["pnl"]
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak * 100)
    return {"trades": len(items), "return_pct": (equity / 1000 - 1) * 100, "profit_factor": gains / losses if losses else None, "maximum_drawdown_pct": drawdown}


def evaluate(open_oos: bool = False, development: Path | None = None) -> dict:
    if open_oos:
        prior = json.loads(development.read_text())
        if prior["decision"] != "PASS_VALIDATION_OPEN_OOS":
            raise ValueError("DEVELOPMENT_DID_NOT_RELEASE_OOS")
    stages = ("oos",) if open_oos else ("train", "validation")
    results = {stage: {} for stage in stages}
    pooled = {stage: [] for stage in stages}
    for asset, path in SOURCES.items():
        all_items = trades(load(path))
        for stage in stages:
            start, end = PERIODS[stage]
            selected = [x for x in all_items if start <= x["entry"] and x["exit"] <= end]
            results[stage][asset] = metrics(selected)
            pooled[stage].extend(selected)
    pooled_metrics = {stage: metrics(sorted(items, key=lambda x: x["exit"])) for stage, items in pooled.items()}
    if open_oos:
        m = pooled_metrics["oos"]
        passed = m["trades"] >= 5 and (m["profit_factor"] or 0) >= 1.10 and m["return_pct"] > 0 and m["maximum_drawdown_pct"] <= 15
        decision = "PASS_DEFENSIVE_ATR_SHOCK_OOS" if passed else "REJECT_DEFENSIVE_ATR_SHOCK_OOS"
    else:
        train, validation = pooled_metrics["train"], pooled_metrics["validation"]
        positive = sum(x["return_pct"] > 0 for x in results["validation"].values())
        passed = train["trades"] >= 20 and (train["profit_factor"] or 0) >= 1.10 and validation["trades"] >= 8 and (validation["profit_factor"] or 0) >= 1.10 and positive >= 2 and validation["maximum_drawdown_pct"] <= 15
        decision = "PASS_VALIDATION_OPEN_OOS" if passed else "REJECT_DEVELOPMENT"
    return {"schema_version": 1, "decision": decision, "results": results, "pooled": pooled_metrics, "oos_accessed": open_oos, "optimized": False, "post_2024_accessed": False, "paper_authorized": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oos", action="store_true")
    parser.add_argument("--development", type=Path)
    args = parser.parse_args()
    result = evaluate(args.oos, args.development)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
