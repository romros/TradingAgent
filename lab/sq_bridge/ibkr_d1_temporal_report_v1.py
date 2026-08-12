#!/usr/bin/env python3
"""Aggregate uncensored D1 Retest orders into an IBKR-cost temporal gate."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def duration_days(value: str) -> float:
    match = re.fullmatch(r"(?:(\d+)d )?(?:(\d+)h )?(?:(\d+)m)?(?:(\d+)s)?", value)
    if not match:
        raise ValueError(f"invalid SQ duration: {value}")
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days + hours / 24 + minutes / 1440 + seconds / 86400


def metrics(rows: list[dict]) -> dict:
    pnl = [row["net_pnl"] for row in rows]
    gross_profit = sum(max(0, value) for value in pnl)
    gross_loss = -sum(min(0, value) for value in pnl)
    equity = peak = drawdown = 0.0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "trades": len(rows),
        "net_profit": round(sum(pnl), 2),
        "net_profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "net_expectancy": round(sum(pnl) / len(pnl), 2) if pnl else None,
        "win_rate": round(sum(value > 0 for value in pnl) / len(pnl), 4) if pnl else None,
        "maximum_closed_trade_drawdown": round(drawdown, 2),
        "average_duration_days": round(
            sum(row["duration_days"] for row in rows) / len(rows), 2) if rows else None,
    }


def build(root: Path, output: Path, round_trip_cost: float = 2.0) -> dict:
    results = []
    for receipt_path in sorted(root.glob("*/run/supervised_retest_receipt.json")):
        receipt = json.loads(receipt_path.read_text())
        manifest_path = Path(receipt["manifest_path"])
        orders_path = Path(receipt["orders_csv_path"])
        if (receipt.get("decision") != "PASS_SUPERVISED_RETEST"
                or receipt.get("holdout_accessed") is not False
                or sha(manifest_path) != receipt["manifest_sha256"]
                or sha(orders_path) != receipt["orders_csv_sha256"]):
            raise ValueError(f"invalid Retest lineage: {receipt_path}")
        manifest = json.loads(manifest_path.read_text())
        discovery = json.loads(Path(manifest["resource_source"]).with_suffix(
            ".manifest.json").read_text())
        periods = discovery["periods"]
        rows = []
        with orders_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                rows.append({
                    "close": datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S").date(),
                    "net_pnl": number(row["Profit/Loss"]) - round_trip_cost,
                    "duration_days": duration_days(row["Time in trade"]),
                })
        segments = {}
        for name in ("train", "validation", "oos"):
            start = datetime.fromisoformat(periods[f"{name}_from"]).date()
            end = datetime.fromisoformat(periods[f"{name}_to"]).date()
            segments[name] = metrics([row for row in rows if start <= row["close"] <= end])
        years = {str(year): metrics([row for row in rows if row["close"].year == year])
                 for year in sorted({row["close"].year for row in rows})}
        positive_year_ratio = sum(row["net_profit"] > 0 for row in years.values()) / len(years)
        passes = (
            segments["validation"]["trades"] >= 20
            and segments["oos"]["trades"] >= 20
            and (segments["validation"]["net_profit_factor"] or 0) >= 1.2
            and (segments["oos"]["net_profit_factor"] or 0) >= 1.2
            and positive_year_ratio >= 0.7
        )
        results.append({
            "case": receipt_path.parents[1].name,
            "candidate_id": receipt["candidate_id"],
            "orders_csv_path": str(orders_path),
            "orders_csv_sha256": sha(orders_path),
            "round_trip_cost": round_trip_cost,
            "segments": segments,
            "years": years,
            "positive_year_ratio": round(positive_year_ratio, 4),
            "passes_temporal_gate": passes,
        })
    if not results:
        raise ValueError("no completed D1 Retests")
    result = {
        "schema_version": 1,
        "decision": "PASS_TEMPORAL_CANDIDATES" if any(
            row["passes_temporal_gate"] for row in results) else "REJECT_TEMPORAL_BATCH",
        "round_trip_cost": round_trip_cost,
        "holdout_accessed": False,
        "evaluated": len(results),
        "passing_cases": [row["case"] for row in results if row["passes_temporal_gate"]],
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--round-trip-cost", type=float, default=2.0)
    args = parser.parse_args()
    result = build(args.root, args.output, args.round_trip_cost)
    print(json.dumps({"decision": result["decision"], "evaluated": result["evaluated"],
                      "passing_cases": result["passing_cases"]}, indent=2))


if __name__ == "__main__":
    main()
