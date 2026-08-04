#!/usr/bin/env python3
"""Local parameter robustness for the two coherent v24 MSFT seeds."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from lab.sq_bridge.msft_close_drift_v24 import load_sq_close, metrics, trades_for


def run(data: Path) -> dict:
    close = load_sq_close(data)
    periods = {"train": ("1999-01-01", "2013-12-31"),
               "validation": ("2014-01-01", "2018-12-31"),
               "oos_internal_non_independent": ("2019-01-01", "2023-12-31")}
    seeds = []
    for centre in (100, 200):
        rows = []
        for sma, roc, threshold, hold in itertools.product(
                [round(centre * .8), centre, round(centre * 1.2)],
                [4, 5, 6], [-1.6, -2.0, -2.4], [4, 5, 6]):
            trades = trades_for(close, sma, roc, threshold, hold)
            result = {name: metrics(trades, *period) for name, period in periods.items()}
            passed = all(result[name]["trades"] >= 25 and
                         (result[name]["profit_factor"] or 0) >= 1.1 and
                         result[name]["return_pct"] > 0
                         for name in ("validation", "oos_internal_non_independent"))
            rows.append({"sma": sma, "roc_days": roc, "threshold_pct": threshold,
                         "hold": hold, "passed": passed, **result})
        passing = [row for row in rows if row["passed"]]
        seeds.append({"seed": f"sma{centre}_roc5_dip2_hold5", "neighbour_count": len(rows),
                      "pass_count": len(passing), "pass_ratio": len(passing) / len(rows),
                      "decision": "ROBUST_CLUSTER" if len(passing) / len(rows) >= .5 else "FRAGILE_CLUSTER",
                      "neighbours": rows})
    return {"schema_version": 1, "cost_bps": 36,
            "scope": "post-selection robustness; historical evidence is non-independent",
            "seeds": seeds, "paper_authorized": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run(args.data); args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps([{key: seed[key] for key in ("seed", "neighbour_count", "pass_count", "pass_ratio", "decision")}
                      for seed in result["seeds"]], indent=2))


if __name__ == "__main__": main()
