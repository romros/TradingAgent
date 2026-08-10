#!/usr/bin/env python3
"""Construeix la validació temporal v4 des de traces OOS congelats."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("+00:00"):
        raise ValueError("Timestamp temporal no UTC")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Timestamp temporal invalid") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("Timestamp temporal no UTC")
    return parsed


def _trade_pnl(rows: object, seen: set[str], after: datetime | None,
               before: datetime | None) -> tuple[list[float], list[datetime]]:
    if not isinstance(rows, list):
        raise ValueError("Trades temporals absents")
    pnl, timestamps = [], []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("trade_id"), str):
            raise ValueError("Trade temporal invalid")
        trade_id = row["trade_id"]
        if not trade_id or trade_id in seen:
            raise ValueError("trade_id temporal duplicat")
        seen.add(trade_id)
        timestamp = _utc(row.get("exit_timestamp"))
        if (timestamps and timestamp <= timestamps[-1]) or (after and timestamp <= after):
            raise ValueError("Trades temporals no ordenats")
        if before and timestamp > before:
            raise ValueError("Trade fora de la seva finestra temporal")
        value = row.get("net_pnl_usdc")
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value)):
            raise ValueError("PnL temporal invalid")
        pnl.append(float(value))
        timestamps.append(timestamp)
    return pnl, timestamps


def evaluate_trace(trace: dict) -> dict:
    if (trace.get("schema_version") != 1
            or trace.get("trace_type") != "temporal_validation_trade_trace"):
        raise ValueError("Schema de trace temporal invalid")
    candidate_id = trace.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id temporal absent")
    if trace.get("capital_usdc") != 200 or trace.get("holdout_accessed") is not False:
        raise ValueError("Trace temporal ha d'usar 200 USDC sense obrir holdout")
    if trace.get("cost_scenario") != "base":
        raise ValueError("La seleccio temporal requereix el cost base congelat")
    cost_hash = trace.get("cost_model_sha256")
    if (not isinstance(cost_hash, str) or len(cost_hash) != 64
            or any(char not in "0123456789abcdef" for char in cost_hash)):
        raise ValueError("Hash del model de costos temporal invalid")

    train_end = _utc(trace.get("train_end_utc"))
    seen: set[str] = set()
    train, train_timestamps = _trade_pnl(
        trace.get("train_trades"), seen, None, train_end)
    if not train:
        raise ValueError("Train temporal buit")
    train_expectancy = sum(train) / len(train)
    if train_expectancy <= 0:
        raise ValueError("Expectativa train no positiva; decay no estimable")

    windows = trace.get("oos_windows")
    if not isinstance(windows, list) or not windows:
        raise ValueError("Finestres OOS absents")
    window_ids, all_oos, window_totals = [], [], []
    previous_end = train_end
    for window in windows:
        if not isinstance(window, dict) or not isinstance(window.get("window_id"), str):
            raise ValueError("Finestra OOS invalida")
        window_id = window["window_id"]
        start, end = _utc(window.get("start_utc")), _utc(window.get("end_utc"))
        if not window_id or window_id in window_ids or start <= previous_end or end <= start:
            raise ValueError("Finestres OOS duplicades, solapades o desordenades")
        values, _ = _trade_pnl(window.get("trades"), seen, start, end)
        window_ids.append(window_id)
        all_oos.extend(values)
        window_totals.append(sum(values))
        previous_end = end
    if window_ids != sorted(window_ids) or not all_oos:
        raise ValueError("Finestres OOS han de ser uniques, ordenades i no buides")
    wins = sum(value for value in all_oos if value > 0)
    losses = -sum(value for value in all_oos if value < 0)
    if losses <= 0:
        raise ValueError("Profit factor OOS no estimable")
    oos_expectancy = sum(all_oos) / len(all_oos)
    equity = peak = 200.0
    maximum_drawdown = 0.0
    for value in all_oos:
        equity += value
        peak = max(peak, equity)
        if peak <= 0:
            raise ValueError("Equity temporal no valida")
        maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak * 100)
    return {
        "candidate_id": candidate_id,
        "oos_trades": len(all_oos),
        "positive_windows_ratio": sum(value > 0 for value in window_totals) / len(window_totals),
        "oos_profit_factor": wins / losses,
        "oos_drawdown_pct": maximum_drawdown,
        "train_oos_expectancy_decay_pct": (train_expectancy - oos_expectancy)
            / train_expectancy * 100,
        "net_expectancy_usdc": oos_expectancy,
    }


def pareto(metrics: dict[str, dict]) -> list[str]:
    selected = []
    for candidate_id, row in metrics.items():
        dominated = any(
            other["net_expectancy_usdc"] >= row["net_expectancy_usdc"]
            and other["positive_windows_ratio"] >= row["positive_windows_ratio"]
            and other["oos_drawdown_pct"] <= row["oos_drawdown_pct"]
            and (other["net_expectancy_usdc"] > row["net_expectancy_usdc"]
                 or other["positive_windows_ratio"] > row["positive_windows_ratio"]
                 or other["oos_drawdown_pct"] < row["oos_drawdown_pct"])
            for other_id, other in metrics.items() if other_id != candidate_id)
        if not dominated:
            selected.append(candidate_id)
    return sorted(selected)


def build_artifact(*, campaign_id: str, trace_paths: list[Path],
                   methodology_path: Path, artifact_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    gate = methodology["temporal_validation"]
    evaluated, paths, hashes = {}, {}, {}
    base = artifact_path.resolve().parent
    for path in trace_paths:
        metrics = evaluate_trace(json.loads(path.read_text()))
        candidate_id = metrics.pop("candidate_id")
        if candidate_id in evaluated:
            raise ValueError("candidate_id temporal duplicat")
        evaluated[candidate_id] = metrics
        paths[candidate_id] = _relative(path, base)
        hashes[candidate_id] = _sha(path)
    if not evaluated:
        raise ValueError("Cal almenys un trace temporal")
    passing = {key: row for key, row in evaluated.items()
               if row["oos_trades"] >= gate["minimum_trades_oos"]
               and row["positive_windows_ratio"] >= gate["minimum_positive_windows_ratio"]
               and row["oos_profit_factor"] >= gate["minimum_oos_profit_factor"]
               and row["oos_drawdown_pct"] <= gate["maximum_oos_drawdown_pct"]
               and row["train_oos_expectancy_decay_pct"]
                   <= gate["maximum_train_oos_expectancy_decay_pct"]}
    selected = pareto(passing) if passing else []
    selected_metrics = {key: evaluated[key] for key in selected}
    artifact = {
        "schema_version": 1, "stage": "temporal_validation",
        "campaign_id": campaign_id, "decision": "PASS" if selected else "REJECT",
        "candidate_ids": selected, "holdout_accessed": False,
        "evidence_class": "observed", "selection_metric": gate["selection_metric"],
        "evaluated_candidate_temporal_metrics": evaluated,
        "candidate_temporal_metrics": selected_metrics,
        "pareto_candidate_ids": selected,
        "temporal_trace_paths": paths, "temporal_trace_sha256": hashes,
    }
    if selected:
        artifact.update({
            "oos_trades": min(row["oos_trades"] for row in selected_metrics.values()),
            "positive_windows_ratio": min(
                row["positive_windows_ratio"] for row in selected_metrics.values()),
            "oos_profit_factor": min(
                row["oos_profit_factor"] for row in selected_metrics.values()),
            "oos_drawdown_pct": max(
                row["oos_drawdown_pct"] for row in selected_metrics.values()),
            "train_oos_expectancy_decay_pct": max(
                row["train_oos_expectancy_decay_pct"] for row in selected_metrics.values()),
        })
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--trace", action="append", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    artifact = build_artifact(
        campaign_id=args.campaign_id, trace_paths=args.trace,
        methodology_path=args.methodology, artifact_path=args.artifact_output)
    print(json.dumps({"decision": artifact["decision"],
                      "candidate_ids": artifact["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
