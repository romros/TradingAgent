#!/usr/bin/env python3
"""Test the consolidated fifth family using positive residual cash only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import lab.sq_bridge.five_edge_residual_margin_v1 as engine

HERE = Path(__file__).resolve().parent
SPEC = HERE / "five_edge_residual_cash_preregistration_v1.json"
LOCK = HERE / "five_edge_residual_cash_preregistration_v1.lock.json"


def verify_freeze() -> None:
    expected = json.loads(LOCK.read_text())["preregistration_sha256"]
    actual = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError("PREREGISTRATION_LOCK_MISMATCH")


def evaluate(sqx: Path, fx: Path, orders: dict[str, Path], strategy_spec: Path) -> dict:
    verify_freeze()
    original_limit = engine.BORROW_LIMIT
    try:
        engine.BORROW_LIMIT = 0.0
        result = engine.evaluate(sqx, fx, orders, strategy_spec)
    finally:
        engine.BORROW_LIMIT = original_limit
    passed = (
        result["cagr_pct"] > result["base"]["cagr_pct"]
        and result["daily_mtm_max_drawdown_pct"] <= 20
        and result["minimum_equity_usd"] > 0
    )
    result["decision"] = (
        "PASS_ADMIT_FIFTH_EDGE_RESIDUAL_CASH"
        if passed else "FAIL_FIFTH_EDGE_RESIDUAL_CASH"
    )
    result["policy"]["borrow_limit_usd"] = 0.0
    result["policy"]["candidate_may_use_only_positive_combined_cash"] = True
    result["candidate"]["extra_financing_usd"] = 0.0
    result["engine_provenance"] = "five_edge_residual_margin_v1 with frozen borrow limit set to zero"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqx", type=Path)
    parser.add_argument("--fx", type=Path, required=True)
    for key in ("cat", "msft", "jpm", "sgln"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--strategy-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        args.sqx, args.fx,
        {key: getattr(args, key) for key in ("cat", "msft", "jpm", "sgln")},
        args.strategy_spec,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
