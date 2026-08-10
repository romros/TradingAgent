#!/usr/bin/env python3
"""Calcula paritat SQ↔Python v4 des de traces congelats, mai des de resums manuals."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def _timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Timestamp invalid a {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Timestamp invalid a {field}: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timestamp sense zona UTC a {field}: {value}")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_trace(trace: dict, expected_source: str | None = None) -> dict:
    if trace.get("schema_version") != 1 or trace.get("trace_type") != "strategy_parity_trace":
        raise ValueError("Schema de trace de paritat invalid")
    if expected_source is not None and trace.get("source") != expected_source:
        raise ValueError(f"Font de trace incorrecta: {trace.get('source')}")
    candidate = trace.get("candidate_id")
    if not isinstance(candidate, str) or not candidate:
        raise ValueError("candidate_id absent al trace")
    candles = [_timestamp(value, "candles") for value in trace.get("candles", [])]
    if candles != sorted(set(candles)):
        raise ValueError("Candles han de ser uniques i ordenades")
    signals = []
    for row in trace.get("signals", []):
        if not isinstance(row, dict) or row.get("direction") not in {"long", "short"}:
            raise ValueError("Signal de paritat invalid")
        signals.append((_timestamp(row.get("timestamp"), "signals"), row["direction"]))
    if signals != sorted(set(signals)):
        raise ValueError("Senyals han de ser unics i ordenats")
    trades = []
    for row in trace.get("trades", []):
        if not isinstance(row, dict) or row.get("direction") not in {"long", "short"}:
            raise ValueError("Trade de paritat invalid")
        pnl = row.get("pnl")
        if not isinstance(pnl, (int, float)) or isinstance(pnl, bool) or not math.isfinite(pnl):
            raise ValueError("PnL de paritat invalid")
        identity = (_timestamp(row.get("entry_timestamp"), "trade.entry"),
                    _timestamp(row.get("exit_timestamp"), "trade.exit"), row["direction"])
        if identity[0] >= identity[1]:
            raise ValueError("Trade amb sortida no posterior a l'entrada")
        trades.append((identity, float(pnl)))
    identities = [identity for identity, _ in trades]
    if identities != sorted(set(identities)):
        raise ValueError("Trades han de ser unics i ordenats")
    candle_set = set(candles)
    if any(timestamp not in candle_set for timestamp, _ in signals):
        raise ValueError("Signal fora de les candles del trace")
    if any(entry not in candle_set or exit_ not in candle_set
           for (entry, exit_, _), _ in trades):
        raise ValueError("Trade fora de les candles del trace")
    return {"candidate_id": candidate, "candles": candles,
            "signals": signals, "trades": dict(trades)}


def _match_rate(left: set, right: set) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _correlation(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    if left == right:
        return 1.0
    if len(left) < 2:
        return 0.0
    left_mean, right_mean = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_var = sum((x - left_mean) ** 2 for x in left)
    right_var = sum((y - right_mean) ** 2 for y in right)
    denominator = math.sqrt(left_var * right_var)
    return numerator / denominator if denominator else 0.0


def compare_traces(sq_trace: dict, python_trace: dict) -> dict:
    sq = validate_trace(sq_trace, "strategyquant")
    py = validate_trace(python_trace, "python")
    if sq["candidate_id"] != py["candidate_id"]:
        raise ValueError("Els traces pertanyen a candidats diferents")
    sq_candles, py_candles = set(sq["candles"]), set(py["candles"])
    sq_signals, py_signals = set(sq["signals"]), set(py["signals"])
    sq_trades, py_trades = sq["trades"], py["trades"]
    matched_trade_ids = sorted(set(sq_trades) & set(py_trades))
    pnl_errors = [abs(sq_trades[key] - py_trades[key]) for key in matched_trade_ids]
    candle_union = sq_candles | py_candles
    return {
        "candidate_id": sq["candidate_id"],
        "sq_candle_count": len(sq_candles),
        "python_candle_count": len(py_candles),
        "common_candle_count": len(sq_candles & py_candles),
        "candle_coverage_pct": (100 * len(sq_candles & py_candles) / len(candle_union)
                                if candle_union else 0.0),
        "sq_signal_count": len(sq_signals),
        "python_signal_count": len(py_signals),
        "matched_signal_count": len(sq_signals & py_signals),
        "signal_match_rate": _match_rate(sq_signals, py_signals),
        "sq_trade_count": len(sq_trades),
        "python_trade_count": len(py_trades),
        "matched_trade_count": len(matched_trade_ids),
        "trade_match_rate": _match_rate(set(sq_trades), set(py_trades)),
        "pnl_correlation": _correlation(
            [sq_trades[key] for key in matched_trade_ids],
            [py_trades[key] for key in matched_trade_ids]),
        "pnl_mean_absolute_error_usdc": (sum(pnl_errors) / len(pnl_errors)
                                         if pnl_errors else math.inf),
        "pnl_max_absolute_error_usdc": max(pnl_errors) if pnl_errors else math.inf,
    }


def build_artifact(*, campaign_id: str, candidate_id: str, sq_trace_path: Path,
                   python_trace_path: Path, methodology_path: Path,
                   report_path: Path, artifact_path: Path) -> dict:
    sq_raw = json.loads(sq_trace_path.read_text())
    python_raw = json.loads(python_trace_path.read_text())
    metrics = compare_traces(sq_raw, python_raw)
    if metrics["candidate_id"] != candidate_id:
        raise ValueError("Candidate lineage mismatch als traces")
    methodology = json.loads(methodology_path.read_text())
    gate = methodology["parity"]
    parity_pass = (
        metrics["matched_signal_count"] >= gate["minimum_matched_signals"]
        and metrics["matched_trade_count"] >= gate["minimum_matched_trades"]
        and metrics["signal_match_rate"] >= gate["minimum_signal_match_rate"]
        and metrics["trade_match_rate"] >= gate["minimum_trade_match_rate"]
        and metrics["candle_coverage_pct"] >= gate["minimum_candle_coverage_pct"]
        and metrics["pnl_correlation"] >= gate["minimum_pnl_correlation"]
        and metrics["pnl_mean_absolute_error_usdc"]
            <= gate["maximum_pnl_mean_absolute_error_usdc"]
        and metrics["pnl_max_absolute_error_usdc"]
            <= gate["maximum_pnl_absolute_error_usdc"])
    report_base = report_path.resolve().parent
    report = {
        "schema_version": 2,
        **metrics,
        "sq_trace_path": _relative(sq_trace_path, report_base),
        "sq_trace_sha256": _sha(sq_trace_path),
        "python_trace_path": _relative(python_trace_path, report_base),
        "python_trace_sha256": _sha(python_trace_path),
        "methodology_sha256": _sha(methodology_path),
        "parity_pass": parity_pass,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    artifact_base = artifact_path.resolve().parent
    artifact = {
        "schema_version": 1, "stage": "parity", "campaign_id": campaign_id,
        "decision": "PASS" if parity_pass else "REJECT", "candidate_ids": [candidate_id],
        "holdout_accessed": False, "evidence_class": "observed",
        "parity_pass": parity_pass,
        "signal_match_rate": metrics["signal_match_rate"],
        "trade_match_rate": metrics["trade_match_rate"],
        "candle_coverage_pct": metrics["candle_coverage_pct"],
        "pnl_correlation": metrics["pnl_correlation"],
        "pnl_mean_absolute_error_usdc": metrics["pnl_mean_absolute_error_usdc"],
        "pnl_max_absolute_error_usdc": metrics["pnl_max_absolute_error_usdc"],
        "matched_signal_count": metrics["matched_signal_count"],
        "matched_trade_count": metrics["matched_trade_count"],
        "parity_report_path": _relative(report_path, artifact_base),
        "parity_report_sha256": _sha(report_path),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--sq-trace", required=True, type=Path)
    parser.add_argument("--python-trace", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--report-output", required=True, type=Path)
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    result = build_artifact(
        campaign_id=args.campaign_id, candidate_id=args.candidate_id,
        sq_trace_path=args.sq_trace, python_trace_path=args.python_trace,
        methodology_path=args.methodology, report_path=args.report_output,
        artifact_path=args.artifact_output)
    print(json.dumps({key: result[key] for key in (
        "decision", "matched_signal_count", "matched_trade_count",
        "signal_match_rate", "trade_match_rate", "pnl_correlation")}, indent=2))


if __name__ == "__main__":
    main()
