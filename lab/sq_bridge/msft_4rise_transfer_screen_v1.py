#!/usr/bin/env python3
"""Frozen cross-asset screen for the four-rising-closes D1 hypothesis."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from lab.sq_bridge.msft_python_validation import load_data, simulate
from lab.sq_bridge.sqx_extract import extract


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metrics(trades: list[dict], cost_bps: float = 20) -> dict:
    values = np.array([row["return"] - cost_bps / 10_000 for row in trades], dtype=float)
    gains = values[values > 0].sum(); losses = -values[values < 0].sum()
    curve = np.r_[1.0, np.cumprod(1 + values)]
    peak = np.maximum.accumulate(curve)
    return {"trades": len(values),
            "profit_factor": float(gains / losses) if losses else None,
            "return_pct": float((curve[-1] - 1) * 100),
            "max_drawdown_pct": float(np.max(1 - curve / peak) * 100)}


def screen(*, preregistration: Path, lock: Path, variants_dir: Path,
           assets: dict[str, Path]) -> dict:
    if json.loads(lock.read_text()).get("sha256") != _sha(preregistration):
        raise ValueError("transfer preregistration lock mismatch")
    spec = json.loads(preregistration.read_text())
    if set(assets) != set(spec["assets"]):
        raise ValueError("asset set differs from preregistration")
    rows = []
    for asset, source in sorted(assets.items()):
        frame = load_data("2017-01-01", "2025-01-01", source)
        variants = []
        for path in sorted(variants_dir.glob("MSFT014_B4_*.sqx")):
            contract = extract(path)
            if contract["translation_status"] != "SUPPORTED_SUBSET":
                raise ValueError(f"unsupported variant: {path.name}")
            stages = {}
            for stage, dates in spec["periods"].items():
                raw = simulate(frame, contract, *dates)
                stages[stage] = _metrics(raw["trades_detail"], spec["roundtrip_cost_bps"])
            passed = all(
                value["trades"] >= spec["gate"]["minimum_trades_each_segment"]
                and (value["profit_factor"] or 0) >= spec["gate"]["minimum_profit_factor_each_segment"]
                and value["return_pct"] > 0
                and value["max_drawdown_pct"] <= spec["gate"]["maximum_drawdown_pct_each_segment"]
                for value in stages.values())
            variants.append({"id": path.stem, "sqx_sha256": _sha(path),
                             "stages": stages, "passes": passed})
        passed_count = sum(row["passes"] for row in variants)
        rows.append({"asset": asset, "source_sha256": _sha(source),
                     "passing_variants": passed_count,
                     "passes_region": passed_count >= spec["gate"]["minimum_passing_variants_of_9"],
                     "variants": variants})
    passing_assets = sum(row["passes_region"] for row in rows)
    passed = passing_assets >= spec["gate"]["minimum_passing_assets_of_3"]
    return {"schema_version": 1,
            "decision": "PASS_NATIVE_TRANSFER_REQUIRED" if passed else "REJECT_NO_CROSS_ASSET_EDGE",
            "preregistration_sha256": _sha(preregistration),
            "passing_assets": passing_assets, "assets": rows,
            "holdout_accessed": False, "native_sq_required": passed,
            "library_admitted": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--variants-dir", type=Path, required=True)
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assets = dict(item.split("=", 1) for item in args.asset)
    result = screen(preregistration=args.preregistration, lock=args.lock,
                    variants_dir=args.variants_dir,
                    assets={key: Path(value) for key, value in assets.items()})
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "passing_assets": result["passing_assets"],
                      "assets": {row["asset"]: row["passing_variants"]
                                 for row in result["assets"]}}, indent=2))


if __name__ == "__main__":
    main()
