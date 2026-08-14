#!/usr/bin/env python3
"""Closed-equity audit for the frozen SXR8 turn-of-month + CAT 0.168 pair.

Research is strictly limited to 2019-2024.  CAT is rebuilt only from annual
through-2024 files, so the canonical file containing 2025 is never opened.
Each strategy owns an independent 1,000-unit sleeve; there is no leverage or
capital transfer between sleeves. Results are evidence, not live authority.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

from cat_0168_transfer_screen_v1 import frozen_orders
from turn_of_month_screen_v1 import load as load_sq, trades as tom_trades


START, END = "2019.01.01", "2024.12.31"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cat(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        if "2025" in path.name:
            raise ValueError("2025+ is sealed")
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row["date"] >= "2025-01-01":
                    raise ValueError("2025+ row is sealed")
                rows.append({"date": row["date"].replace("-", "."),
                             **{key: float(row[key]) for key in ("open", "high", "low", "close")}})
    rows.sort(key=lambda row: row["date"])
    if len({row["date"] for row in rows}) != len(rows):
        raise ValueError("duplicate CAT dates")
    return rows


def cat_sleeve(rows: list[dict], capital: float, start: str = START, end: str = END) -> list[dict]:
    equity = capital
    out = []
    for order in frozen_orders(rows, start, end):
        entry = order["open_price"] * 1.001
        exit_price = order["close_price"] * .999
        shares = math.floor(equity / entry)
        if shares < 1:
            raise ValueError("CAT sleeve cannot buy one whole share")
        fee = max(1.0, .005 * shares)
        pnl = shares * (exit_price - entry) - 2 * fee
        equity += pnl
        out.append({"date": order["close_time"].date().isoformat(), "pnl": pnl,
                    "equity": equity, "return": pnl / (equity - pnl)})
    return out


def sxr8_sleeve(path: Path, capital: float, start: str = START, end: str = END) -> list[dict]:
    frame = load_sq(path)
    raw = tom_trades(frame, date.fromisoformat(start.replace(".", "-")),
                     date.fromisoformat(end.replace(".", "-")))
    equity = capital
    out = []
    # EUR 1.25 per order plus 10 bps adverse round-trip slippage.
    for close_date, gross_return in raw:
        net_return = gross_return - (2 * 1.25 / equity) - .001
        pnl = equity * net_return
        equity += pnl
        out.append({"date": close_date.isoformat(), "pnl": pnl,
                    "equity": equity, "return": net_return})
    return out


def metrics(events: list[dict], initial: float) -> dict:
    equity, peak, drawdown = initial, initial, 0.0
    wins = losses = 0.0
    monthly = defaultdict(float)
    for event in sorted(events, key=lambda row: row["date"]):
        equity += event["pnl"]
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
        monthly[event["date"][:7]] += event["pnl"]
        if event["pnl"] > 0:
            wins += event["pnl"]
        elif event["pnl"] < 0:
            losses -= event["pnl"]
    return {"initial_capital": initial, "final_equity": round(equity, 6),
            "return_pct": round((equity / initial - 1) * 100, 6),
            "events": len(events), "profit_factor": round(wins / losses, 6) if losses else None,
            "max_drawdown_pct_closed_equity": round(drawdown * 100, 6),
            "positive_months": sum(x > 0 for x in monthly.values()),
            "active_months": len(monthly)}


def monthly_correlation(left: list[dict], right: list[dict]) -> dict:
    def sums(rows):
        out = defaultdict(float)
        for row in rows:
            out[row["date"][:7]] += row["return"]
        return out
    a, b = sums(left), sums(right)
    keys = sorted(set(a) | set(b))
    x, y = [a[k] for k in keys], [b[k] for k in keys]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    den = (sum((v-mx)**2 for v in x) * sum((v-my)**2 for v in y)) ** .5
    return {"months": len(keys), "correlation_zero_when_inactive":
            round(sum((u-mx)*(v-my) for u, v in zip(x, y)) / den, 6) if den else None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sxr8", required=True, type=Path)
    ap.add_argument("--cat", action="append", required=True, type=Path)
    ap.add_argument("--sleeve-capital", default=1000.0, type=float)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.sleeve_capital <= 0:
        raise ValueError("capital must be positive")
    cat_rows = load_cat(args.cat)
    def period(start: str, end: str) -> dict:
        cat = cat_sleeve(cat_rows, args.sleeve_capital, start, end)
        sxr8 = sxr8_sleeve(args.sxr8, args.sleeve_capital, start, end)
        combined = [{"date": x["date"], "pnl": x["pnl"]} for x in cat + sxr8]
        sm, cm = metrics(sxr8, args.sleeve_capital), metrics(cat, args.sleeve_capital)
        return {"strategies": {"SXR8_TURN_OF_MONTH": sm, "CAT_0168": cm},
                "portfolio": metrics(combined, 2 * args.sleeve_capital),
                "diversification": monthly_correlation(sxr8, cat),
                "both_positive": sm["return_pct"] > 0 and cm["return_pct"] > 0}
    full = period(START, END)
    forward = period("2022.01.01", END)
    report = {"schema_version": 1, "period": "2019-01-01/2024-12-31",
              "allocation": "two independent equal sleeves; no leverage; no rebalancing",
              "costs": "CAT fixed commissions + 10bps each side; SXR8 EUR1.25/order + 10bps round-trip",
              "inputs_sha256": {str(args.sxr8): sha(args.sxr8),
                                 **{str(p): sha(p) for p in args.cat}},
              "full_2019_2024": full,
              "forward_validation_oos_2022_2024": forward,
              "decision": "TWO_EDGE_SHADOW_PORTFOLIO" if full["both_positive"] and forward["both_positive"] else "REJECT",
              "limitations": ["CAT has only 21 trades in the 2024 OOS year, below its frozen 60-trade release gate",
                              "closed-equity drawdown ignores intratrade mark-to-market",
                              "different sleeve currencies are treated as accounting units; FX conversion is excluded"],
              "holdout_2025_accessed": False, "orders_sent": 0,
              "paper_authorized": False, "live_authorized": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
