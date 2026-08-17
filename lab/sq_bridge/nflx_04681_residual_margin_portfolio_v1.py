#!/usr/bin/env python3
"""Frozen marginal test of capped NFLX 0.4681 on the canonical four-edge account."""
from __future__ import annotations

import argparse
import csv
import json
import math
from bisect import bisect_right
from datetime import date, datetime
from pathlib import Path

try:
    from .four_edge_position_leverage_audit_v2 import audit, sha
except ImportError:
    from four_edge_position_leverage_audit_v2 import audit, sha

EXPECTED_ORDERS = "fcc9c31e8cda9eb3cb8bf732b082d497e5822a7fd87535c09909c7553653fcc0"
EXPECTED_D1 = "12c140360eb22d9c489d796e3215e565f0e46b6b0918b206585bf577bae2b818"
START, END = date(2022, 1, 1), date(2024, 12, 31)
CAPITAL = 2000.0
TOTAL_BORROW_LIMIT = 2000.0
NFLX_NOTIONAL_CAP = 1000.0
RATE = 0.08
SLIPPAGE = 0.001
BASE_CAGR = 15.99959
BASE_DD = 15.915973


def drawdown(rows):
    peak_value, peak_day = rows[0][1], rows[0][0]
    maximum, pair = 0.0, (peak_day, peak_day)
    for day, value in rows:
        if value > peak_value:
            peak_value, peak_day = value, day
        decline = (peak_value - value) / peak_value * 100
        if decline > maximum:
            maximum, pair = decline, (peak_day, day)
    return maximum, pair


def prior(days, values, day):
    index = bisect_right(days, day) - 1
    return values[index] if index >= 0 else values[0]


def load_closes(path: Path) -> dict[date, float]:
    if sha(path) != EXPECTED_D1:
        raise ValueError("frozen NFLX D1 source mismatch")
    out = {}
    with path.open(newline="") as stream:
        for row in csv.reader(stream):
            day = datetime.strptime(row[0], "%Y.%m.%d").date()
            if START <= day <= END:
                out[day] = float(row[5])
    return out


def load_trades(path: Path) -> list[dict]:
    if sha(path) != EXPECTED_ORDERS:
        raise ValueError("frozen NFLX order source mismatch")
    out = []
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            opened = datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S").date()
            closed = datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S").date()
            if START <= opened <= END:
                out.append({"open": opened, "close": closed,
                            "open_price": float(row["Open price"]),
                            "close_price": float(row["Close price"]),
                            "close_type": row["Close type"]})
    return out


def evaluate(sqx: Path, fx: Path, base_orders: dict[str, Path], nflx_orders: Path,
             nflx_d1: Path) -> dict:
    base = audit(sqx, fx, base_orders, include_daily=True)["scenarios"]["stress"]
    base_equity = {date.fromisoformat(x["date"]): x["equity_usd"] for x in base.pop("daily_equity")}
    base_cash = {date.fromisoformat(x["date"]): x["cash_usd"] for x in base.pop("daily_cash")}
    bd, bv = sorted(base_equity), [base_equity[x] for x in sorted(base_equity)]
    cd, cv = sorted(base_cash), [base_cash[x] for x in sorted(base_cash)]
    closes = load_closes(nflx_d1)
    nd, nv = sorted(closes), [closes[x] for x in sorted(closes)]
    trades = load_trades(nflx_orders)
    entries = {x["open"]: x for x in trades}
    exits = {x["close"]: x for x in trades}
    days = sorted(set(bd) | set(closes))

    cash = 0.0
    position = None
    completed = []
    skipped_margin = skipped_cap = 0
    financing = 0.0
    curve = []
    previous = days[0]
    for day in days:
        active_base_cash = prior(cd, cv, day)
        extra_borrow = max(-(active_base_cash + cash), 0.0) - max(-active_base_cash, 0.0)
        charge = max(extra_borrow, 0.0) * RATE * (day - previous).days / 365.2425
        cash -= charge
        financing += charge

        if position is not None and day == position["close"]:
            proceeds = position["shares"] * position["close_price"] * (1 - SLIPPAGE) - 1.0
            cash += proceeds
            completed.append(proceeds - position["cost"])
            position = None

        if position is None and day in entries:
            trade = entries[day]
            entry = trade["open_price"] * (1 + SLIPPAGE)
            shares = math.floor((NFLX_NOTIONAL_CAP - 1.0) / entry)
            cost = shares * entry + 1.0
            if not shares:
                skipped_cap += 1
            elif active_base_cash + cash - cost < -TOTAL_BORROW_LIMIT:
                skipped_margin += 1
            else:
                position = {**trade, "shares": shares, "cost": cost}
                cash -= cost

        mark = 0.0
        if position is not None:
            mark_price = prior(nd, nv, day)
            mark = position["shares"] * mark_price * (1 - SLIPPAGE) - 1.0
        curve.append((day, prior(bd, bv, day) + cash + mark))
        previous = day

    maximum, pair = drawdown(curve)
    final = curve[-1][1]
    years = (END - START).days / 365.2425
    cagr = ((final / CAPITAL) ** (1 / years) - 1) * 100
    gains = sum(max(x, 0.0) for x in completed)
    losses = sum(max(-x, 0.0) for x in completed)
    passed = cagr > BASE_CAGR and maximum <= 20.0 and min(v for _, v in curve) > 0
    return {
        "schema_version": 1,
        "decision": "PASS_NFLX_04681_MARGINAL_GATE" if passed else "FAIL_NFLX_04681_MARGINAL_GATE",
        "period": f"{START}/{END}",
        "initial_capital_usd": CAPITAL,
        "account_borrow_limit_usd": TOTAL_BORROW_LIMIT,
        "candidate_notional_cap_usd": NFLX_NOTIONAL_CAP,
        "final_equity_usd": round(final, 6),
        "net_return_pct": round((final / CAPITAL - 1) * 100, 6),
        "cagr_pct": round(cagr, 6),
        "daily_mtm_max_drawdown_pct": round(maximum, 6),
        "drawdown_peak_date": str(pair[0]), "drawdown_trough_date": str(pair[1]),
        "minimum_equity_usd": round(min(v for _, v in curve), 6),
        "candidate": {
            "signals": len(trades), "executed_trades": len(completed),
            "skipped_notional_cap": skipped_cap, "skipped_account_margin": skipped_margin,
            "profit_factor_before_financing": round(gains / losses, 6) if losses else None,
            "net_pnl_before_financing_usd": round(sum(completed), 6),
            "extra_financing_usd": round(financing, 6),
            "open_position_at_boundary": position is not None,
        },
        "base": {"return_pct": 56.041808, "cagr_pct": BASE_CAGR, "drawdown_pct": BASE_DD},
        "classification": "preregistered_fixed_rule_marginal_portfolio_test",
        "limitations": [
            "The canonical four-edge portfolio has execution priority.",
            "NFLX uses whole shares, a fixed $1000 notional cap, 10 bps slippage per side, $1 per order and 8% incremental borrowing.",
            "This is historical research, not paper/live authorization or a return promise.",
        ],
        "sources": {"nflx_orders_sha256": EXPECTED_ORDERS, "nflx_d1_sha256": EXPECTED_D1},
        "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqx", type=Path); parser.add_argument("--fx", required=True, type=Path)
    for key in ("cat", "msft", "jpm", "sgln"):
        parser.add_argument(f"--{key}", required=True, type=Path)
    parser.add_argument("--nflx-orders", required=True, type=Path)
    parser.add_argument("--nflx-d1", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.sqx, args.fx, {k: getattr(args, k) for k in ("cat", "msft", "jpm", "sgln")},
                      args.nflx_orders, args.nflx_d1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
