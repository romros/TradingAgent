#!/usr/bin/env python3
"""Deterministic preregistered MSFT close-to-close drift falsification."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd


def load_sq_close(path: Path) -> pd.Series:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            normalized = {str(k).strip().lower(): v for k, v in row.items() if k}
            date = (normalized.get("date") or "").replace(".", "-")
            if date and normalized.get("close"):
                rows.append((pd.Timestamp(date), float(normalized["close"])))
    series = pd.Series(dict(rows), dtype=float).sort_index()
    if series.empty or series.index.has_duplicates or (series <= 0).any():
        raise ValueError("INVALID_SQ_CLOSE_SERIES")
    return series


def trades_for(close: pd.Series, sma: int, roc_days: int, threshold: int, hold: int) -> list[dict]:
    # Signal observed at D-1. Entry at D close, never at an uncertified open.
    trend_before_pullback = close.shift(1) > close.rolling(sma).mean().shift(1)
    signal = (trend_before_pullback &
              (close.pct_change(roc_days).mul(100) <= threshold)).shift(1).fillna(False)
    trades = []
    next_allowed = 0
    for i in np.flatnonzero(signal.to_numpy()):
        if i < next_allowed or i + hold >= len(close):
            continue
        entry, exit_ = float(close.iloc[i]), float(close.iloc[i + hold])
        trades.append({"entry": close.index[i].date().isoformat(),
                       "exit": close.index[i + hold].date().isoformat(),
                       "gross_return": exit_ / entry - 1, "bars": hold})
        next_allowed = i + hold + 1
    return trades


def metrics(trades: list[dict], start: str, end: str, cost_bps: int = 36) -> dict:
    values = [t["gross_return"] - cost_bps / 10_000 for t in trades if start <= t["entry"] <= end]
    wins = sum(v for v in values if v > 0); losses = -sum(v for v in values if v < 0)
    curve = peak = 1.0; max_dd = 0.0
    years = {}
    for trade, value in zip([t for t in trades if start <= t["entry"] <= end], values):
        curve *= 1 + value; peak = max(peak, curve); max_dd = max(max_dd, 1 - curve / peak)
        years[trade["entry"][:4]] = years.get(trade["entry"][:4], 1.0) * (1 + value)
    return {"trades": len(values), "profit_factor": wins / losses if losses else None,
            "return_pct": (curve - 1) * 100, "max_drawdown_pct": max_dd * 100,
            "positive_year_ratio": sum(v > 1 for v in years.values()) / len(years) if years else 0,
            "year_count": len(years)}


def random_timing_p(close: pd.Series, candidate: dict, start: str, end: str, runs: int = 1000) -> float:
    selected = [t for t in candidate["trades"] if start <= t["entry"] <= end]
    if not selected:
        return 1.0
    eligible = close.loc[start:end]
    hold = candidate["hold"]
    full_trend = close.shift(2) > close.rolling(candidate["sma"]).mean().shift(2)
    trend = full_trend.reindex(eligible.index).fillna(False).to_numpy()
    possible = [i for i in range(0, max(0, len(eligible) - hold)) if trend[i]]
    observed = metrics(selected, start, end)["return_pct"]
    seed = int(hashlib.sha256(candidate["id"].encode()).hexdigest()[:16], 16)
    rng = random.Random(seed); better = 0
    for _ in range(runs):
        shuffled = possible.copy(); rng.shuffle(shuffled); indices = []
        for index in shuffled:
            if all(abs(index - chosen) > hold for chosen in indices):
                indices.append(index)
                if len(indices) == len(selected):
                    break
        if len(indices) < len(selected):
            return 1.0
        indices.sort()
        random_trades = [{"entry": eligible.index[i].date().isoformat(),
                          "gross_return": float(eligible.iloc[i + hold] / eligible.iloc[i] - 1)} for i in indices]
        better += metrics(random_trades, start, end)["return_pct"] >= observed
    return (better + 1) / (runs + 1)


def periodic_drift_return(close: pd.Series, trade_count: int, hold: int, start: str, end: str) -> float:
    """Deterministic evenly-spaced long exposure with matched trade count/holding."""
    sample = close.loc[start:end]
    if trade_count <= 0 or len(sample) <= hold:
        return 0.0
    indices = np.linspace(0, len(sample) - hold - 1, trade_count, dtype=int)
    trades = [{"entry": sample.index[i].date().isoformat(),
               "gross_return": float(sample.iloc[i + hold] / sample.iloc[i] - 1)} for i in indices]
    return metrics(trades, start, end)["return_pct"]


def run(data_path: Path, methodology_path: Path) -> dict:
    method = json.loads(methodology_path.read_text()); close = load_sq_close(data_path)
    periods = method["periods"]; gate = method["frozen_gate"]; candidates = []
    grid = method["grid"]
    for sma, roc, threshold, hold in itertools.product(
            grid["trend_sma"], grid["pullback_roc_days"], grid["pullback_threshold_pct"], grid["holding_days"]):
        ident = f"sma{sma}_roc{roc}_dip{abs(threshold)}_hold{hold}"
        trades = trades_for(close, sma, roc, threshold, hold)
        row = {"id": ident, "sma": sma, "roc_days": roc, "threshold_pct": threshold,
               "hold": hold, "trades": trades,
               "train": metrics(trades, *periods["train"]),
               "validation": metrics(trades, *periods["validation"]),
               "oos_internal_non_independent": metrics(trades, *periods["oos_internal_non_independent"])}
        row["validation_random_timing_p"] = random_timing_p(close, row, *periods["validation"])
        row["validation_periodic_drift_return_pct"] = periodic_drift_return(
            close, row["validation"]["trades"], hold, *periods["validation"])
        row["validation_excess_vs_periodic_drift_pct"] = (
            row["validation"]["return_pct"] - row["validation_periodic_drift_return_pct"])
        reasons = []
        if row["validation"]["trades"] < gate["minimum_validation_trades"]: reasons.append("VALIDATION_TRADES_LT_25")
        if (row["validation"]["profit_factor"] or 0) < gate["minimum_validation_stress_pf"]: reasons.append("VALIDATION_STRESS_PF_LT_1_10")
        if (row["oos_internal_non_independent"]["profit_factor"] or 0) < gate["minimum_oos_stress_pf"]: reasons.append("OOS_STRESS_PF_LT_1_10")
        if row["oos_internal_non_independent"]["positive_year_ratio"] < gate["minimum_positive_year_ratio"]: reasons.append("POSITIVE_YEAR_RATIO_LT_0_60")
        if row["oos_internal_non_independent"]["max_drawdown_pct"] > gate["maximum_oos_drawdown_pct"]: reasons.append("OOS_DD_GT_25")
        if row["validation_random_timing_p"] > gate["maximum_random_timing_empirical_p"]: reasons.append("RANDOM_TIMING_P_GT_0_10")
        if row["validation_excess_vs_periodic_drift_pct"] <= gate["minimum_excess_return_vs_matched_periodic_drift_pct"]: reasons.append("NO_EXCESS_VS_PERIODIC_DRIFT")
        row["reasons"] = reasons; row["passed"] = not reasons
        del row["trades"]
        candidates.append(row)
    passed = [row for row in candidates if row["passed"]]
    buy_hold = {name: float(close.loc[start:end].iloc[-1] / close.loc[start:end].iloc[0] - 1) * 100
                for name, (start, end) in periods.items() if end is not None and not close.loc[start:end].empty}
    return {"schema_version": 1, "methodology_sha256": hashlib.sha256(methodology_path.read_bytes()).hexdigest(),
            "data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(), "candidate_count": len(candidates),
            "buy_and_hold_return_pct": buy_hold,
            "pass_count": len(passed), "decision": "FORWARD_PAPER_COHORT" if passed else "REJECT_FAMILY",
            "selection_warning": "historical periods are non-independent; PASS cannot authorize live",
            "passed": passed, "candidates": candidates, "paper_authorized": False, "live_authorized": False}


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--data", type=Path, required=True)
    p.add_argument("--methodology", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(); result = run(args.data, args.methodology)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"candidate_count": result["candidate_count"], "pass_count": result["pass_count"],
                      "decision": result["decision"], "passed_ids": [x["id"] for x in result["passed"]]}, indent=2))


if __name__ == "__main__": main()
