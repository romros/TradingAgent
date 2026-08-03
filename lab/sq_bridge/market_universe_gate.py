#!/usr/bin/env python3
"""Freeze a reproducible research-source decision before strategy discovery."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_xau(report_path: Path) -> dict:
    report = json.loads(report_path.read_text())
    opened = report.get("returns_market_open", {})
    reasons = []
    if report.get("symbol") != "XAUUSD":
        reasons.append("WRONG_SYMBOL")
    if report.get("source_a") != "ostium_realtime" or report.get("source_b") != "dukascopy":
        reasons.append("WRONG_SOURCE_PAIR")
    if report.get("aligned_count", 0) < 5_000:
        reasons.append("TOO_FEW_ALIGNED_M1")
    if opened.get("corr", 0) < 0.95:
        reasons.append("RETURN_CORRELATION_BELOW_0_95")
    if opened.get("dir_agree_filtered_pct", 0) < 95:
        reasons.append("FILTERED_DIRECTION_BELOW_95_PCT")
    if report.get("verdict") != "PASS_BACKTEST":
        reasons.append("UPSTREAM_NOT_PASS_BACKTEST")
    return {
        "market": "XAUUSD",
        "decision": "PASS_RESEARCH" if not reasons else "BLOCK",
        "live_eligible": False,
        "reasons": reasons or ["DUKASCOPY_ACCEPTED_AS_RESEARCH_PROXY_ONLY"],
        "evidence": {
            "path": str(report_path),
            "sha256": sha256(report_path),
            "aligned_m1": report.get("aligned_count"),
            "overlap_minutes": report.get("overlap", {}).get("overlap_minutes"),
            "market_open_return_corr": opened.get("corr"),
            "market_open_filtered_direction_pct": opened.get("dir_agree_filtered_pct"),
            "upstream_verdict": report.get("verdict"),
        },
        "limitation": "Short recent overlap permits research, not paper/live certification.",
    }


def _optional_json(path: Path | None) -> dict | None:
    return json.loads(path.read_text()) if path is not None and path.is_file() else None


def evaluate_btc(native_ostium_paths: list[Path], coverage_path: Path | None = None,
                 parity_path: Path | None = None) -> dict:
    present = sorted(str(path) for path in native_ostium_paths if path.exists())
    coverage = _optional_json(coverage_path)
    parity = _optional_json(parity_path)
    if not present:
        decision, reasons = "BLOCK", ["NO_NATIVE_OSTIUM_HISTORY_FOR_BTCUSDT_PROXY_PARITY"]
    elif not coverage or coverage.get("decision") != "READY_FOR_PARITY":
        decision, reasons = "WARMING", ["NATIVE_OSTIUM_HISTORY_NOT_MATURE"]
    elif not parity or parity.get("decision") != "PASS_RESEARCH_OHLC":
        decision, reasons = "BLOCK", ["BTCUSDT_BTCUSD_PARITY_NOT_PASSED"]
    else:
        decision, reasons = "PASS_RESEARCH", ["NATIVE_HISTORY_MATURE_AND_PROXY_PARITY_PASSED"]
    return {
        "market": "BTCUSD",
        "decision": decision,
        "live_eligible": False,
        "reasons": reasons,
        "native_ostium_paths_present": present,
        "coverage_artifact": str(coverage_path) if coverage_path else None,
        "coverage_decision": coverage.get("decision") if coverage else None,
        "parity_artifact": str(parity_path) if parity_path else None,
        "parity_decision": parity.get("decision") if parity else None,
        "limitation": "BTCUSDT in SQ cannot proxy BTC/USD on Ostium until price and execution parity are measured.",
    }


def build(report_path: Path, btc_paths: list[Path], coverage_path: Path | None = None,
          parity_path: Path | None = None) -> dict:
    markets = [evaluate_xau(report_path), evaluate_btc(btc_paths, coverage_path, parity_path)]
    selected = [item["market"] for item in markets if item["decision"] == "PASS_RESEARCH"]
    return {
        "schema_version": 1,
        "gate_id": "alquimia-market-universe-v2-maturity-and-parity",
        "purpose": "Select a market for new discovery without using prior strategy performance.",
        "markets": markets,
        "selected_for_discovery": selected,
        "paper_or_live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xau-compat-report", type=Path, required=True)
    parser.add_argument("--btc-native-ostium-path", type=Path, action="append", default=[])
    parser.add_argument("--btc-coverage-report", type=Path)
    parser.add_argument("--btc-parity-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.xau_compat_report, args.btc_native_ostium_path,
                   args.btc_coverage_report, args.btc_parity_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
