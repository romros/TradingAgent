#!/usr/bin/env python3
"""Open the preregistered XLE 2024 OOS only after validation release."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from lab.sq_bridge.xle_monthly_tsmom_screen_v1 import load, metrics, returns, sha


def evaluate(source: Path, validation_receipt: Path) -> dict:
    receipt = json.loads(validation_receipt.read_text())
    if receipt["decision"] != "PASS_VALIDATION_FREEZE_BEFORE_OOS":
        raise ValueError("VALIDATION_DID_NOT_RELEASE_OOS")
    if receipt["source_sha256"] != sha(source):
        raise ValueError("SOURCE_CHANGED_AFTER_VALIDATION")
    data = load(source)
    result = {}
    for name, lookback in (("M6", 126), ("M12", 252)):
        oos = metrics(returns(data, lookback, dt.date(2024, 1, 1),
                              dt.date(2024, 12, 31)),
                      dt.date(2024, 1, 1), dt.date(2024, 12, 31))
        combined = metrics(
            returns(data, lookback, dt.date(2022, 1, 1), dt.date(2024, 12, 31)),
            dt.date(2022, 1, 1), dt.date(2024, 12, 31),
        )
        result[name] = {"oos_2024": oos, "validation_plus_oos": combined}
    central = result["M12"]["validation_plus_oos"]
    passed = (
        all(result[name]["oos_2024"]["total_return"] > 0 for name in ("M6", "M12"))
        and (central["annualized_monthly_sharpe"] or -999) >= 0.5
        and central["maximum_drawdown"] <= 0.25
    )
    return {
        "schema_version": 1,
        "decision": "PASS_GROSS_OOS_REQUIRE_COST_AUDIT" if passed else "REJECT_GROSS_OOS",
        "source_sha256": sha(source),
        "validation_receipt_sha256": sha(validation_receipt),
        "results": result,
        "known_train_warning": "M6 and M12 were both negative in 2017-11-15/2021",
        "optimized": False,
        "holdout_2025_plus_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.source, args.validation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
