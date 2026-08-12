#!/usr/bin/env python3
"""Fail-closed $2k IBKR feasibility gate for D1 finalists at one-unit minimum."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def number(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def load(case: dict) -> list[dict]:
    rows = []
    with Path(case["orders_csv_path"]).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            rows.append({
                "open": datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S"),
                "close": datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S"),
                # SQ uses a dot for price/size but locale comma for money fields.
                "open_price": float(row["Open price"]), "size": float(row["Size"]),
                "net_pnl": number(row["Profit/Loss"]) - 2.0,
                "mae": number(row["MAE ($)"]) - 2.0,
            })
    return rows


def subject_metrics(rows: list[dict], capital: float, leverage: float) -> dict:
    events = []
    for index, row in enumerate(rows):
        events.extend(((row["open"], 1, index), (row["close"], -1, index)))
    active, max_positions, max_margin = set(), 0, 0.0
    # Open before close at the same timestamp is deliberately conservative.
    for _, kind, index in sorted(events, key=lambda item: (item[0], -item[1])):
        if kind == 1:
            active.add(index)
        else:
            active.discard(index)
        max_positions = max(max_positions, len(active))
        max_margin = max(max_margin, sum(
            rows[i]["open_price"] * rows[i]["size"] / leverage for i in active))
    worst_loss = min(row["net_pnl"] for row in rows)
    worst_mae = min(row["mae"] for row in rows)
    return {
        "capital_usd": capital, "minimum_size_units": 1,
        "assumed_max_leverage": leverage,
        "worst_closed_trade_usd": round(worst_loss, 2),
        "worst_closed_trade_pct_capital": round(-worst_loss / capital * 100, 2),
        "worst_observed_mae_usd": round(worst_mae, 2),
        "worst_observed_mae_pct_capital": round(-worst_mae / capital * 100, 2),
        "maximum_concurrent_positions": max_positions,
        "approximate_maximum_initial_margin_usd": round(max_margin, 2),
        "approximate_maximum_margin_pct_capital": round(max_margin / capital * 100, 2),
    }


def minimum_capital(metrics: dict, *, maximum_risk_pct: float = 1.5,
                    maximum_margin_pct: float = 60,
                    maximum_mc_drawdown_pct: float = 25) -> dict:
    """Return transparent capital floors; the largest constraint controls."""
    floors = {
        "observed_mae": (-metrics["worst_observed_mae_usd"]
                         / (maximum_risk_pct / 100)),
        "initial_margin": (metrics["approximate_maximum_initial_margin_usd"]
                           / (maximum_margin_pct / 100)),
        "mc_drawdown_p95": (metrics["mc_drawdown_p95_usd"]
                            / (maximum_mc_drawdown_pct / 100)),
    }
    controlling = max(floors, key=floors.get)
    return {
        "minimum_capital_usd": round(floors[controlling], 2),
        "controlling_constraint": controlling,
        "constraint_floors_usd": {key: round(value, 2)
                                  for key, value in floors.items()},
        "limits_pct": {
            "observed_mae": maximum_risk_pct,
            "initial_margin": maximum_margin_pct,
            "mc_drawdown_p95": maximum_mc_drawdown_pct,
        },
    }


def build(temporal_path: Path, robustness_path: Path, portfolio_path: Path,
          output: Path, capital: float = 2000, leverage: float = 16) -> dict:
    temporal = json.loads(temporal_path.read_text())
    robustness = json.loads(robustness_path.read_text())
    portfolios = json.loads(portfolio_path.read_text())
    cases = {row["case"]: row for row in temporal["results"]}
    robust = {row["subject_id"]: row for row in robustness["results"]}
    subjects = [(case, [case]) for case in temporal["passing_cases"]]
    if portfolios.get("passing_portfolios"):
        top = portfolios["passing_portfolios"][0]
        subjects.append((top["portfolio_id"], top["cases"]))
    results = []
    for subject_id, members in subjects:
        rows = [trade for case in members for trade in load(cases[case])]
        measured = subject_metrics(rows, capital, leverage)
        mc = robust[subject_id]["monte_carlo"]
        measured.update({
            "mc_drawdown_p95_usd": mc["drawdown_p95"],
            "mc_drawdown_p95_pct_capital": round(mc["drawdown_p95"] / capital * 100, 2),
            "mc_drawdown_p99_usd": mc["drawdown_p99"],
            "mc_drawdown_p99_pct_capital": round(mc["drawdown_p99"] / capital * 100, 2),
        })
        measured["capital_floor"] = minimum_capital(measured)
        passes = (measured["worst_observed_mae_pct_capital"] <= 1.5
                  and measured["approximate_maximum_margin_pct_capital"] <= 60
                  and measured["mc_drawdown_p95_pct_capital"] <= 25)
        results.append({"subject_id": subject_id, "cases": members,
                        "metrics": measured, "passes_small_account_gate": passes})
    result = {"schema_version": 1,
              "decision": "PASS_SMALL_ACCOUNT" if any(
                  row["passes_small_account_gate"] for row in results) else "REJECT_SMALL_ACCOUNT",
              "capital_usd": capital, "holdout_accessed": False,
              "paper_authorized": False, "live_authorized": False,
              "results": results}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temporal", type=Path, required=True)
    parser.add_argument("--robustness", type=Path, required=True)
    parser.add_argument("--portfolios", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capital", type=float, default=2000)
    parser.add_argument("--leverage", type=float, default=16)
    args = parser.parse_args()
    print(json.dumps(build(args.temporal, args.robustness, args.portfolios,
                           args.output, args.capital, args.leverage), indent=2))


if __name__ == "__main__":
    main()
