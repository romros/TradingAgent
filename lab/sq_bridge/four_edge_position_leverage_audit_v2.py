#!/usr/bin/env python3
"""Frozen net audit of the four-edge 2x position-only portfolio."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from bisect import bisect_right
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from .sq_portfolio_daily_equity_v1 import decode
    from .sq_portfolio_ibkr_cost_fx_v1 import SCENARIOS
    from .four_edge_net_mtm_audit_v1 import drawdown, load_fx, asof
except ImportError:
    from sq_portfolio_daily_equity_v1 import decode
    from sq_portfolio_ibkr_cost_fx_v1 import SCENARIOS
    from four_edge_net_mtm_audit_v1 import drawdown, load_fx, asof

EXPECTED_SQX = "5e419d22050c0a376543f24fe4f64567bc53d26d16f83b5dd3097016a89d5a71"
EXPECTED_FX = "f95006726de866df21bea8ca0c3a1e7f9d082600b57d04199ab37201b7b48e21"
EXPECTED_ORDERS = {
    "cat": "d4c062fef38bdcb8c1c4707a43277628c15d74148ff4297316482ef419db2d16",
    "msft": "deb336714c3437f1e94c1f85f9c4e5cc3b4a9f523fe95199a3ce880ac66038e7",
    "jpm": "3c9478bfad8cc2872499d7e36f748af11be679f1f8f605c6fcc2ca538b8103e8",
    "sgln": "bf3b71e0fae85dffddf47443637997576098596574ed923e1564519e2190ed5e",
}
CAPITAL = 2000.0
SLEEVE = 1000.0
RATE = 0.08
START, END = date(2022, 1, 1), date(2024, 12, 31)
ACCEPTED = re.compile(r"Order ACCEPTED '([^/]+)/.*?OpenTime=([0-9.]+) [^|]+\|OpenPrice=\$([0-9.]+).*?\]=([0-9.]+)")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_trades(paths: dict[str, Path]) -> list[dict]:
    trades = []
    for key, path in paths.items():
        if sha(path) != EXPECTED_ORDERS[key]:
            raise ValueError(f"frozen {key} orders hash mismatch")
        with path.open(newline="") as stream:
            for row in csv.DictReader(stream, delimiter=";"):
                trades.append({
                    "key": key,
                    "open": datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S").date(),
                    "close": datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S").date(),
                    "open_price": float(row["Open price"]),
                    "close_price": float(row["Close price"]),
                })
    return trades


def audit(sqx: Path, fx_path: Path, order_paths: dict[str, Path]) -> dict:
    if sha(sqx) != EXPECTED_SQX or sha(fx_path) != EXPECTED_FX:
        raise ValueError("frozen SQX/FX hash mismatch")
    trades = read_trades(order_paths)
    fx_days, fx_values = load_fx(fx_path)
    with zipfile.ZipFile(sqx) as archive:
        members = {n: decode(archive.read(n)) for n in archive.namelist() if n.endswith("dailyEquity.bin")}
        log = ET.fromstring(archive.read("settings.xml")).find(".//PortfolioComposerLog").text or ""
    portfolio = {d: pnl for d, pnl in members["Results/Portfolio/dailyEquity.bin"] if START <= d <= END}
    gold_name = next(n for n in members if "SGLN_" in n)
    gold = sorted((d, pnl) for d, pnl in members[gold_name] if d <= END)
    gold_days, gold_pnls = [x[0] for x in gold], [x[1] for x in gold]

    sizes = {}
    for line in dict.fromkeys(x for x in log.splitlines() if "Order ACCEPTED" in x):
        match = ACCEPTED.search(line)
        if not match:
            raise ValueError("accepted-order parse mismatch")
        day = date(*map(int, match.group(2).split(".")))
        sizes[(match.group(1).split("_")[0].lower(), day)] = float(match.group(4))
    gold_trade = next(t for t in trades if t["key"] == "sgln")
    gold_entry_fx = asof(fx_days, fx_values, gold_trade["open"])
    actual_gold_size = int(SLEEVE / (gold_trade["open_price"] * gold_entry_fx))
    for trade in trades:
        if trade["key"] == "sgln":
            trade["size"] = actual_gold_size
        else:
            candidates = [v for (name, day), v in sizes.items() if day == trade["open"] and trade["key"] in name]
            if len(candidates) != 1:
                raise ValueError(f"cannot match native size for {trade['key']} {trade['open']}")
            trade["size"] = candidates[0]

    scenarios = {}
    for scenario, cost in SCENARIOS.items():
        costs, events = {}, {}
        for trade in trades:
            if trade["key"] == "sgln":
                open_fx = asof(fx_days, fx_values, trade["open"])
                close_fx = asof(fx_days, fx_values, trade["close"])
                buy = trade["size"] * trade["open_price"] * open_fx
                sell = trade["size"] * trade["close_price"] * close_fx
                fee = 2 * cost["uk_order_gbp"] * open_fx + (buy + sell) * (cost["uk_bps_side"] + cost["fx_bps_side"]) / 10000
            else:
                buy = trade["size"] * trade["open_price"]
                sell = trade["size"] * trade["close_price"]
                fee = 2 * cost["us_order"] + (buy + sell) * cost["us_bps_side"] / 10000
            costs[trade["open"]] = costs.get(trade["open"], 0.0) + fee
            events.setdefault(trade["open"], []).append((1, -buy - fee))
            events.setdefault(trade["close"], []).append((0, sell))

        cash, financing, accrued_cost, previous = CAPITAL, 0.0, 0.0, START
        rows, max_borrow = [], 0.0
        for day in sorted(portfolio):
            elapsed = (day - previous).days
            charge = max(-cash, 0.0) * RATE * elapsed / 365.2425
            financing += charge
            cash -= charge
            for _, amount in sorted(events.get(day, [])):
                cash += amount
            accrued_cost += costs.get(day, 0.0)
            max_borrow = max(max_borrow, max(-cash, 0.0))
            gold_index = bisect_right(gold_days, day) - 1
            sq_gold_pnl = gold_pnls[gold_index] if gold_index >= 0 else 0.0
            corrected_gold_pnl = 0.0 if day < gold_trade["open"] else actual_gold_size * (
                (gold_trade["open_price"] + sq_gold_pnl / 36.0) * asof(fx_days, fx_values, day)
                - gold_trade["open_price"] * gold_entry_fx)
            equity = CAPITAL + portfolio[day] - sq_gold_pnl + corrected_gold_pnl - accrued_cost - financing
            rows.append((day, equity))
            previous = day
        final = rows[-1][1]
        scenarios[scenario] = {
            "final_equity_usd": round(final, 6),
            "net_return_pct": round((final / CAPITAL - 1) * 100, 6),
            "minimum_equity_usd": round(min(v for _, v in rows), 6),
            "costs_usd": round(accrued_cost, 6),
            "position_only_financing_usd": round(financing, 6),
            "maximum_cash_borrow_usd": round(max_borrow, 6),
            **drawdown(rows),
        }
    stress = scenarios["stress"]
    spy_return, spy_dd = 26.928, 23.406
    passed = stress["net_return_pct"] > spy_return and stress["daily_mtm_max_drawdown_pct"] <= spy_dd and stress["minimum_equity_usd"] > 0
    return {
        "schema_version": 2,
        "decision": "PASS_BEATS_SPY_POSITION_ONLY_LEVERAGE" if passed else "FAIL_POSITION_ONLY_LEVERAGE_GATE",
        "period": f"{START}/{END}", "initial_capital_usd": CAPITAL,
        "gross_target_exposure_usd": 4000, "broker_leverage": 2,
        "positions": len(trades), "sgln_whole_shares_usd_corrected": actual_gold_size,
        "benchmark_gate": {"spy_return_pct": spy_return, "spy_drawdown_pct": spy_dd},
        "scenarios": scenarios,
        "limitations": [
            "Borrowing is reconstructed from dated entry/exit cash flows and charged only while cash is negative.",
            "Round-trip costs are charged on entry; this is conservative timing.",
            "SGLN is resized in USD using frozen ECB GBPUSD and replaces SQ's GBP-as-USD accounting.",
            "This is historical research, not paper/live authorization or a return promise."
        ],
        "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqx", type=Path); parser.add_argument("--fx", required=True, type=Path)
    for key in EXPECTED_ORDERS: parser.add_argument(f"--{key}", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.sqx, args.fx, {k: getattr(args, k) for k in EXPECTED_ORDERS})
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
