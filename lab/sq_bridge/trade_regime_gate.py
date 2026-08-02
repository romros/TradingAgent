#!/usr/bin/env python3
"""Deterministic temporal concentration and trade-distribution gate for SQ CSV."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from trade_cost_gate import _metrics_pnls, _nearest_rank, _number


def evaluate(path: Path, runs: int = 10000, seed: int = 20260802) -> dict:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            opened = datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S")
            closed = datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S")
            rows.append({"pnl": _number(row["Profit/Loss"]), "mae": _number(row["MAE ($)"]),
                         "mfe": _number(row["MFE ($)"]), "opened": opened, "closed": closed,
                         "hours": (closed - opened).total_seconds() / 3600,
                         "close_type": row["Close type"], "side": row["Type"]})
    if not rows:
        raise ValueError("CSV_WITHOUT_TRADES")
    pnls = [row["pnl"] for row in rows]
    yearly: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        yearly[row["closed"].year].append(row["pnl"])
    year_metrics = {str(year): _metrics_pnls(values) for year, values in sorted(yearly.items())}
    positive_year_ratio = sum(m["net_pnl_usdc"] > 0 for m in year_metrics.values()) / len(year_metrics)
    positive_pnl = sorted((value for value in pnls if value > 0), reverse=True)
    gross_profit = sum(positive_pnl)
    top5_share = sum(positive_pnl[:5]) / gross_profit if gross_profit else 1.0
    rng = random.Random(seed)
    boot_totals, omission_totals = [], []
    keep = max(1, round(len(pnls) * .9))
    for _ in range(runs):
        boot_totals.append(sum(rng.choice(pnls) for _ in pnls))
        omission_totals.append(sum(rng.sample(pnls, keep)))
    without_top = {}
    for count in (1, 3, 5):
        removed = set(sorted(range(len(pnls)), key=lambda i: pnls[i], reverse=True)[:count])
        without_top[str(count)] = round(sum(v for i, v in enumerate(pnls) if i not in removed), 8)
    checks = {
        "positive_year_ratio_gte_60pct": positive_year_ratio >= .6,
        "top5_gross_profit_share_lte_50pct": top5_share <= .5,
        "bootstrap_p05_positive": _nearest_rank(boot_totals, .05) > 0,
        "omit_10pct_p05_positive": _nearest_rank(omission_totals, .05) > 0,
    }
    return {
        "schema_version": 1, "source": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "metrics": _metrics_pnls(pnls), "yearly": year_metrics,
        "positive_year_ratio": round(positive_year_ratio, 8),
        "top5_gross_profit_share": round(top5_share, 8),
        "duration_hours": {"median": round(_nearest_rank([r["hours"] for r in rows], .5), 4),
                           "p95": round(_nearest_rank([r["hours"] for r in rows], .95), 4),
                           "max": round(max(r["hours"] for r in rows), 4)},
        "without_top_trades_net_pnl": without_top,
        "bootstrap": {"runs": runs, "seed": seed,
                      "p05_net_pnl": round(_nearest_rank(boot_totals, .05), 8),
                      "omit_10pct_p05_net_pnl": round(_nearest_rank(omission_totals, .05), 8)},
        "close_types": {name: sum(r["close_type"] == name for r in rows)
                        for name in sorted({r["close_type"] for r in rows})},
        "checks": checks, "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=10000)
    args = parser.parse_args()
    result = evaluate(args.orders, args.runs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "metrics": result["metrics"],
                      "positive_year_ratio": result["positive_year_ratio"],
                      "top5_gross_profit_share": result["top5_gross_profit_share"],
                      "duration_hours": result["duration_hours"],
                      "bootstrap": result["bootstrap"], "checks": result["checks"]}, indent=2))


if __name__ == "__main__":
    main()
