#!/usr/bin/env python3
"""Fail-closed market-data preflight before creating a new Alquimia family."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def coverage_summary(path: Path) -> dict:
    if not path.exists():
        return {"available": False, "done_months": 0, "rows": 0, "from": None, "to": None}
    data = json.loads(path.read_text())
    done = [(month, item) for month, item in data.get("months", {}).items()
            if item.get("status") == "done" and item.get("rows", 0) > 0]
    if not done:
        return {"available": False, "done_months": 0, "rows": 0, "from": None, "to": None}
    done.sort()
    return {"available": True, "done_months": len(done),
            "rows": sum(item["rows"] for _, item in done),
            "from": done[0][0], "to": done[-1][0],
            "last_updated": data.get("last_updated")}


def registry_observations(paths: list[Path], symbol: str) -> list[dict]:
    observations = []
    for path in paths:
        if not path.exists():
            continue
        item = json.loads(path.read_text()).get(symbol)
        if item:
            observations.append({"registry": str(path), **item})
    return sorted(observations, key=lambda item: (item.get("asof_ts", 0), item["registry"]))


def ostium_storage_summary(root: Path, symbol: str) -> dict:
    directory = root / symbol
    files = sorted(directory.rglob("*.parquet")) if directory.exists() else []
    return {"available": bool(files), "files": len(files),
            "bytes": sum(path.stat().st_size for path in files),
            "paths": [str(path) for path in files]}


def evaluate_market(symbol: str, bs_root: Path, registry_paths: list[Path]) -> dict:
    historical = coverage_summary(bs_root / "datafiles/historical_parquet/_coverage" / f"{symbol}_tf1m.json")
    observations = registry_observations(registry_paths, symbol)
    current = observations[-1] if observations else None
    ostium = ostium_storage_summary(bs_root / "datafiles/historical_parquet_ostium_v1", symbol)
    conflict = len({(item.get("status"), item.get("allowed_for_backtest")) for item in observations}) > 1
    if not historical["available"]:
        decision = "BLOCK_HISTORICAL_SOURCE"
        reasons = ["No checksummed Dukascopy coverage index with completed months."]
    elif current is None:
        decision = "BLOCK_NO_OSTIUM_PARITY"
        reasons = ["Historical source exists, but no Ostium compatibility observation exists."]
    elif not current.get("allowed_for_backtest", False):
        decision = "BLOCK_CURRENT_PARITY"
        reasons = ["The newest compatibility observation does not authorize the proxy for backtesting."]
    else:
        decision = "PASS_RESEARCH_PROXY_ONLY"
        reasons = ["Historical coverage and newest compatibility observation allow proxy research."]
    if conflict:
        reasons.append("Compatibility registries disagree; newest asof_ts is authoritative and fail-closed.")
    return {"symbol": symbol, "decision": decision, "reasons": reasons,
            "historical_dukascopy": historical, "ostium_native_storage": ostium,
            "compatibility_observations": observations, "current_compatibility": current,
            "registry_conflict": conflict, "paper_or_live_authorized": False}


def run(bs_root: Path, symbols: list[str], registry_paths: list[Path]) -> dict:
    markets = [evaluate_market(symbol, bs_root, registry_paths) for symbol in symbols]
    eligible = [item["symbol"] for item in markets if item["decision"] == "PASS_RESEARCH_PROXY_ONLY"]
    return {"schema_version": 1, "preflight_id": "alquimia-market-data-v22",
            "policy": "newest compatibility observation wins; missing or conflicting evidence fails closed",
            "brokerage_service_root": str(bs_root), "markets": markets,
            "research_proxy_eligible_symbols": eligible,
            "d1_equity_campaign_authorized": any(symbol in eligible for symbol in ("MSFT", "NVDA", "NDXUSD")),
            "strategy_campaign_authorized": bool(eligible),
            "global_holdout_accessed": False, "performance_metrics_accessed": False,
            "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bs-root", type=Path, required=True)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--registry", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.bs_root, args.symbols, args.registry)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"eligible": result["research_proxy_eligible_symbols"],
                      "d1_equity_campaign_authorized": result["d1_equity_campaign_authorized"],
                      "decisions": {item["symbol"]: item["decision"] for item in result["markets"]}}, indent=2))


if __name__ == "__main__":
    main()
