#!/usr/bin/env python3
"""Capture and verify SQ's native Monte Carlo confidence-level table."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable


EXPECTED_COLUMNS = ["NetProfit", "Drawdown", "ReturnDDRatio", "RExpectancy"]
EXPECTED_LEVELS = [0, 50, 60, 70, 80, 90, 92, 95, 97, 98, 99, 100]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=45) as response:
        return json.loads(response.read().decode())


def capture(*, base_url: str, project: str, databank: str, strategy: str,
            method: str, source_sqx: Path, requested_simulations: int,
            persisted_simulations: int, fetch: Callable[[str], dict] = _get_json) -> dict:
    if not source_sqx.is_file() or not 0 < persisted_simulations <= requested_simulations:
        raise ValueError("NATIVE_MC_PERCENTILES_SOURCE_INVALID")
    root = base_url.rstrip("/")
    views = fetch(f"{root}/rtresults/viewsGetViews?type=rt")
    default = next((row for row in views.get("views", [])
                    if row.get("name") == "Default"), None)
    columns = [row.get("class") for row in (default or {}).get("columns", [])]
    if columns != EXPECTED_COLUMNS:
        raise ValueError("NATIVE_MC_PERCENTILES_COLUMNS_INVALID")
    params = urllib.parse.urlencode({
        "project": project, "databank": databank, "strategy": strategy,
        "methodName": method, "view": "Default", "width": 1200, "height": 800,
    })
    raw = fetch(f"{root}/rtresults/printConfLevels?{params}")
    settings = raw.get("settings") or {}
    if (raw.get("success") != "ok"
            or settings.get("simulations") != requested_simulations):
        raise ValueError("NATIVE_MC_PERCENTILES_SETTINGS_INVALID")
    rows = []
    for expected_level, row in zip(EXPECTED_LEVELS, raw.get("rows", []), strict=True):
        values = row.get("data") or []
        label = "Original" if expected_level == 0 else f"{expected_level} %"
        if len(values) != 5 or values[0] != label or row.get("id") != f"r{expected_level}":
            raise ValueError("NATIVE_MC_PERCENTILES_ROW_INVALID")
        metrics = {key: float(value) for key, value in zip(columns, values[1:], strict=True)}
        if any(not math.isfinite(value) for value in metrics.values()):
            raise ValueError("NATIVE_MC_PERCENTILES_VALUE_INVALID")
        rows.append({"confidence_level_pct": expected_level, **metrics})
    if len(rows) != len(EXPECTED_LEVELS):
        raise ValueError("NATIVE_MC_PERCENTILES_LEVELS_INCOMPLETE")
    missing = requested_simulations - persisted_simulations
    worst = rows[-1]
    adjusted_profitable_lower_bound = (
        persisted_simulations / requested_simulations if worst["NetProfit"] > 0 else 0.0)
    return {
        "schema_version": 1,
        "artifact_type": "strategyquant_native_mc_percentiles",
        "decision": "DIAGNOSTIC_PASS_CANONICAL_RUN_COUNT_INCOMPLETE",
        "project": project, "databank": databank, "strategy": strategy,
        "method": method, "settings": settings, "columns": columns, "rows": rows,
        "requested_simulations": requested_simulations,
        "persisted_simulations": persisted_simulations,
        "missing_simulations_counted_as_failures": missing,
        "adjusted_profitable_ratio_lower_bound": adjusted_profitable_lower_bound,
        "source_sqx_path": str(source_sqx.resolve()),
        "source_sqx_sha256": _sha(source_sqx),
        "canonical_robustness_authorized": False,
        "holdout_accessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--project", required=True)
    parser.add_argument("--databank", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--method", default="MonteCarloRetest")
    parser.add_argument("--source-sqx", required=True, type=Path)
    parser.add_argument("--requested-simulations", required=True, type=int)
    parser.add_argument("--persisted-simulations", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture(
        base_url=args.base_url, project=args.project, databank=args.databank,
        strategy=args.strategy, method=args.method, source_sqx=args.source_sqx,
        requested_simulations=args.requested_simulations,
        persisted_simulations=args.persisted_simulations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "worst": result["rows"][-1],
                      "adjusted_profitable_ratio_lower_bound":
                          result["adjusted_profitable_ratio_lower_bound"]}, indent=2))


if __name__ == "__main__":
    main()
