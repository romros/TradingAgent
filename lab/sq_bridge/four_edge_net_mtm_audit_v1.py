#!/usr/bin/env python3
"""Frozen daily net mark-to-market audit for the four-edge SQ portfolio."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from bisect import bisect_right
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

from sq_portfolio_daily_equity_v1 import decode
from sq_portfolio_ibkr_cost_fx_v1 import SCENARIOS

ACCEPTED = re.compile(
    r"Order ACCEPTED '([^/]+)/.*?OpenTime=([0-9.]+) [^|]+\|OpenPrice=\$([0-9.]+).*?\]=([0-9.]+)"
)
EXPECTED_SQX = "8a10d42afb4a41fd316cbef18ec7f80c2151e2f092d7698a0e593d0a1dc1637a"
EXPECTED_FX = "f95006726de866df21bea8ca0c3a1e7f9d082600b57d04199ab37201b7b48e21"
START = date(2022, 1, 1)
END = date(2024, 12, 31)
CAPITAL = 2000.0
SLEEVE = 500.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_fx(path: Path) -> tuple[list[date], list[float]]:
    with path.open(newline="") as stream:
        pairs = [(date.fromisoformat(r["date"]), float(r["usd_per_gbp"])) for r in csv.DictReader(stream)]
    pairs.sort()
    return [p[0] for p in pairs], [p[1] for p in pairs]


def asof(days: list[date], values: list[float], day: date) -> float:
    index = bisect_right(days, day) - 1
    if index < 0:
        raise ValueError(f"no FX on/before {day}")
    return values[index]


def drawdown(rows: list[tuple[date, float]]) -> dict:
    peak = rows[0][1]
    peak_day = rows[0][0]
    maximum = 0.0
    pair = (peak_day, peak_day)
    for day, equity in rows:
        if equity > peak:
            peak, peak_day = equity, day
        value = (peak - equity) / peak * 100
        if value > maximum:
            maximum, pair = value, (peak_day, day)
    return {
        "daily_mtm_max_drawdown_pct": round(maximum, 6),
        "drawdown_peak_date": str(pair[0]),
        "drawdown_trough_date": str(pair[1]),
    }


def audit(sqx: Path, fx_path: Path) -> dict:
    if sha(sqx) != EXPECTED_SQX or sha(fx_path) != EXPECTED_FX:
        raise ValueError("frozen input hash mismatch")
    fx_days, fx_values = load_fx(fx_path)
    with zipfile.ZipFile(sqx) as archive:
        members = {n: decode(archive.read(n)) for n in archive.namelist() if n.endswith("dailyEquity.bin")}
        node = ET.fromstring(archive.read("settings.xml")).find(".//PortfolioComposerLog")
        log = node.text or ""
    portfolio_name = "Results/Portfolio/dailyEquity.bin"
    gold_name = next(n for n in members if "SGLN_" in n)
    portfolio = {d: pnl for d, pnl in members[portfolio_name] if START <= d <= END}
    gold = sorted((d, pnl) for d, pnl in members[gold_name] if d <= END)
    gold_days = [d for d, _ in gold]
    gold_pnls = [p for _, p in gold]
    accepted_lines = list(dict.fromkeys(line for line in log.splitlines() if "Order ACCEPTED" in line))
    orders = []
    for line in accepted_lines:
        match = ACCEPTED.search(line)
        if not match:
            raise ValueError("accepted-order parse mismatch")
        year, month, day = map(int, match.group(2).split("."))
        orders.append({"strategy": match.group(1), "date": date(year, month, day), "price": float(match.group(3)), "size": float(match.group(4))})
    gold_orders = [o for o in orders if o["strategy"].startswith("SGLN_")]
    if len(gold_orders) != 1:
        raise ValueError("expected exactly one SGLN entry")
    gold_order = gold_orders[0]
    entry_fx = asof(fx_days, fx_values, gold_order["date"])
    actual_gold_size = int(SLEEVE / (gold_order["price"] * entry_fx))
    if actual_gold_size < 1:
        raise ValueError("SGLN sleeve cannot buy a whole share")

    scenarios = {}
    for scenario, cost in SCENARIOS.items():
        dated_costs: dict[date, float] = {}
        for order in orders:
            if order is gold_order:
                notional = actual_gold_size * order["price"] * entry_fx
                full_roundtrip = 2 * cost["uk_order_gbp"] * entry_fx + 2 * notional * (cost["uk_bps_side"] + cost["fx_bps_side"]) / 10000
            else:
                notional = order["price"] * order["size"]
                full_roundtrip = 2 * cost["us_order"] + 2 * notional * cost["us_bps_side"] / 10000
            dated_costs[order["date"]] = dated_costs.get(order["date"], 0.0) + full_roundtrip
        rows = []
        accrued_cost = 0.0
        cost_events = sorted(dated_costs.items())
        cost_index = 0
        for day in sorted(portfolio):
            while cost_index < len(cost_events) and cost_events[cost_index][0] <= day:
                accrued_cost += cost_events[cost_index][1]
                cost_index += 1
            gold_index = bisect_right(gold_days, day) - 1
            sq_gold_pnl = gold_pnls[gold_index] if gold_index >= 0 else 0.0
            if day < gold_order["date"]:
                corrected_gold_pnl = 0.0
            else:
                current_gbp = gold_order["price"] + sq_gold_pnl / gold_order["size"]
                corrected_gold_pnl = actual_gold_size * (current_gbp * asof(fx_days, fx_values, day) - gold_order["price"] * entry_fx)
            equity = CAPITAL + portfolio[day] - sq_gold_pnl + corrected_gold_pnl - accrued_cost
            rows.append((day, equity))
        final_equity = rows[-1][1]
        scenario_result = {
            "final_equity_usd": round(final_equity, 6),
            "net_return_pct": round((final_equity / CAPITAL - 1) * 100, 6),
            "minimum_equity_usd": round(min(v for _, v in rows), 6),
            "full_roundtrip_costs_accrued_upfront_usd": round(accrued_cost, 6),
            **drawdown(rows),
        }
        scenarios[scenario] = scenario_result
    stress = scenarios["stress"]
    passed = stress["net_return_pct"] > 0 and stress["daily_mtm_max_drawdown_pct"] <= 15 and stress["minimum_equity_usd"] > 0
    return {
        "schema_version": 1,
        "decision": "PASS_ADMIT_SGLN_AS_CAPPED_PORTFOLIO_COMPONENT" if passed else "FAIL_KEEP_SGLN_CONDITIONAL",
        "period": f"{START}/{END}",
        "initial_capital_usd": CAPITAL,
        "sleeve_budget_usd": SLEEVE,
        "sgln_maximum_weight_pct": 25,
        "positions": len(orders),
        "sgln_whole_shares": actual_gold_size,
        "scenarios": scenarios,
        "limitations": [
            "Round-trip costs are charged completely on entry, a conservative timing assumption.",
            "Final return is the 2024-12-31 mark-to-market value; SQ's synthetic 2025-01-01 EndTest liquidation is deliberately outside the sealed market-data window.",
            "Public indicative commissions are not a substitute for an actual IBKR account statement.",
            "This admits diversification use only; standalone SGLN still fails its frozen 20% drawdown gate.",
            "No paper or live trading is authorized."
        ],
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqx", type=Path)
    parser.add_argument("--fx", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.sqx, args.fx)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
