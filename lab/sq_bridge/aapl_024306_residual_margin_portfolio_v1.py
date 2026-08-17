#!/usr/bin/env python3
"""Measure AAPL 0.24306 as one capped residual-margin fifth sleeve."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path

from lab.sq_bridge.five_edge_daily_mtm_v1 import drawdown
from lab.sq_bridge.four_edge_position_leverage_audit_v2 import audit


CAPITAL = 2000.0
NOTIONAL_CAP = 500.0
FINANCING_RATE = 0.08
BASE_CAGR = 15.99959


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value: str) -> float:
    return float(value.replace(",", "."))


def load_orders(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    result = []
    for row in rows:
        opened = date.fromisoformat(row["Open time"][:10].replace(".", "-"))
        closed = date.fromisoformat(row["Close time"][:10].replace(".", "-"))
        if date(2023, 1, 1) <= opened <= date(2024, 12, 31):
            result.append({"opened": opened, "closed": closed,
                           "entry": number(row["Open price"]),
                           "exit": number(row["Close price"])})
    return result


def daily_closes(path: Path) -> dict[date, float]:
    values = {}
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            day = date.fromisoformat(row[0].replace(".", "-"))
            if date(2022, 1, 1) <= day <= date(2024, 12, 31):
                values[day] = float(row[5])
    return values


def evaluate(sqx: Path, fx: Path, orders_path: Path, h1_path: Path) -> dict:
    base_orders = {
        key: sqx.parent / f"orders-{key}-floor1000.csv"
        for key in ("cat", "msft", "jpm", "sgln")
    }
    audited = audit(sqx, fx, base_orders, include_daily=True)["scenarios"]["stress"]
    base = [
        (date.fromisoformat(row["date"]), row["equity_usd"])
        for row in audited["daily_equity"]
    ]
    closes = daily_closes(h1_path)
    orders = load_orders(orders_path)
    by_open = {row["opened"]: row for row in orders}
    if len(by_open) != len(orders):
        raise ValueError("multiple AAPL entries on one day are unsupported")
    position = None
    realized = 0.0
    financing = 0.0
    candidate_curve = []
    closed = []
    for day in sorted(closes):
        if position is not None and day == position["closed"]:
            exit_price = position["exit"] * .999
            proceeds = position["shares"] * exit_price - 1.0
            days = (day - position["opened"]).days
            carry = position["notional"] * FINANCING_RATE * days / 365.2425
            pnl = proceeds - position["entry_cost"] - carry
            realized += pnl
            financing += carry
            closed.append(pnl)
            position = None
        if day in by_open:
            if position is not None:
                raise ValueError("overlapping candidate positions")
            order = by_open[day]
            entry = order["entry"] * 1.001
            shares = math.floor((NOTIONAL_CAP - 1.0) / entry)
            if shares < 1:
                raise ValueError("fifth sleeve cannot buy one AAPL share")
            cost = shares * entry + 1.0
            position = {**order, "shares": shares, "entry_cost": cost,
                        "notional": shares * entry}
            # H1/TICK brackets can enter and exit within the same session.
            if position["closed"] == day:
                exit_price = position["exit"] * .999
                proceeds = position["shares"] * exit_price - 1.0
                pnl = proceeds - position["entry_cost"]
                realized += pnl
                closed.append(pnl)
                position = None
        mark = realized
        if position is not None:
            elapsed = (day - position["opened"]).days
            accrued = position["notional"] * FINANCING_RATE * elapsed / 365.2425
            mark += position["shares"] * closes[day] * .999 - 1.0 \
                    - position["entry_cost"] - accrued
        candidate_curve.append((day, mark))
    if position is not None:
        raise ValueError("open AAPL position at sealed boundary")
    candidate_map = dict(candidate_curve)
    combined = [(day, equity + candidate_map.get(day, 0.0)) for day, equity in base]
    maximum, pair = drawdown(combined)
    final = combined[-1][1]
    years = (date(2024, 12, 31) - date(2022, 1, 1)).days / 365.2425
    cagr = ((final / CAPITAL) ** (1 / years) - 1) * 100
    gains = sum(max(value, 0) for value in closed)
    losses = sum(max(-value, 0) for value in closed)
    checks = {"cagr_improves_base": cagr > BASE_CAGR,
              "drawdown_at_most_20pct": maximum <= 20,
              "candidate_net_positive": sum(closed) > 0}
    return {
        "schema_version": 1,
        "decision": "PASS_ADMIT_AAPL_024306_AS_FIFTH_EDGE" if all(checks.values())
                    else "REJECT_AAPL_024306_PORTFOLIO_MARGINAL",
        "period": "2022-01-01/2024-12-31",
        "initial_capital_usd": CAPITAL,
        "candidate_policy": "base priority; one AAPL sleeve capped at USD500 borrowed only while open",
        "candidate_closed_trades": len(closed),
        "candidate_net_pnl_usd": round(sum(closed), 6),
        "candidate_profit_factor": round(gains / losses, 6) if losses else None,
        "candidate_financing_usd": round(financing, 6),
        "combined_final_equity_usd": round(final, 6),
        "combined_return_pct": round((final / CAPITAL - 1) * 100, 6),
        "combined_cagr_pct": round(cagr, 6),
        "combined_daily_mtm_drawdown_pct": round(maximum, 6),
        "drawdown_peak_date": str(pair[0]),
        "drawdown_trough_date": str(pair[1]),
        "base": {"cagr_pct": BASE_CAGR, "return_pct": 56.041808,
                 "drawdown_pct": 15.915973},
        "checks": checks,
        "inputs_sha256": {"portfolio_sqx": sha256(sqx), "fx": sha256(fx),
                           "aapl_orders": sha256(orders_path), "aapl_h1": sha256(h1_path)},
        "post_2024_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio-sqx", required=True, type=Path)
    parser.add_argument("--fx", required=True, type=Path)
    parser.add_argument("--aapl-orders", required=True, type=Path)
    parser.add_argument("--aapl-h1", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.portfolio_sqx, args.fx, args.aapl_orders, args.aapl_h1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
