#!/usr/bin/env python3
"""Small-account feasibility audit for the four-strategy research portfolio.

This deliberately keeps four fixed 25% compartments.  Cash left because a
whole share cannot be bought remains idle inside that compartment; it is not
silently lent to another strategy.  That makes the test reproducible and more
conservative than the earlier four independent USD 1,000 sleeve diagnostic.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cat_msft_jpm_portfolio_v1 import load_cat, load_jpm, jpm_sleeve
from three_strategy_portfolio_v1 import load_msft, msft_sleeve
from two_strategy_portfolio_v1 import cat_sleeve, metrics
from gold_tsmom_confirmation_screen_v1 import load as load_gold


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gold_whole_units(path: Path, capital: float, start: str, end: str) -> list[dict]:
    """Execute frozen TSMOM12 with whole SGLN units.

    Yahoo quotes SGLN.L in GBp, so prices are divided by 100.  For this
    feasibility screen GBP and account currency are held at 1:1.  That is an
    explicit conservative/approximate boundary, not a claim of FX parity.
    """
    prices = load_gold(path)
    months: dict[tuple[int, int], list[dt.date]] = {}
    for day in sorted(prices):
        months.setdefault((day.year, day.month), []).append(day)
    keys = sorted(months)
    lo, hi = (dt.date.fromisoformat(value) for value in (start, end))
    cash = float(capital)
    units = 0
    previous_equity = float(capital)
    out: list[dict] = []
    for index in range(12, len(keys) - 1):
        current, following = keys[index], keys[index + 1]
        if following[0] * 12 + following[1] != current[0] * 12 + current[1] + 1:
            continue
        signal_day = months[current][-1]
        trade_day = months[following][0]
        if not lo <= trade_day <= hi:
            continue
        desired = prices[signal_day][1] > prices[months[keys[index - 12]][-1]][1]
        raw_open = prices[trade_day][0] / 100.0
        if desired and units == 0:
            buy_price = raw_open * 1.0005
            units = math.floor((cash - 1.25) / buy_price)
            if units > 0:
                cash -= units * buy_price + 1.25
        elif not desired and units > 0:
            sell_price = raw_open * 0.9995
            cash += units * sell_price - 1.25
            units = 0
        equity = cash + units * raw_open
        pnl = equity - previous_equity
        out.append({"date": trade_day.isoformat(), "pnl": pnl, "equity": equity,
                    "return": pnl / previous_equity if previous_equity else 0.0})
        previous_equity = equity
    return out


def audit(cat_path: Path, msft_path: Path, jpm_path: Path, gold_path: Path,
          total_capital: float, start: str = "2022-01-01", end: str = "2024-12-31") -> dict:
    sleeve = total_capital / 4.0
    failures: dict[str, str] = {}
    try:
        cat = cat_sleeve(load_cat(cat_path), sleeve, start.replace("-", "."), end.replace("-", "."))
    except ValueError as exc:
        cat = []
        failures["CAT_0168"] = str(exc)
    legs = {
        "CAT_0168": cat,
        "MSFT_CAPITULATION": msft_sleeve(load_msft(msft_path), sleeve, start, end),
        "JPM_MOMENTUM60": jpm_sleeve(load_jpm(jpm_path), sleeve, start, end),
        "SGLN_TSMOM12": gold_whole_units(gold_path, sleeve, start, end),
    }
    events = [{"date": row["date"], "pnl": row["pnl"]} for rows in legs.values() for row in rows]
    result = metrics(events, total_capital)
    result["capital_per_fixed_compartment"] = sleeve
    result["strategies"] = {name: metrics(rows, sleeve) for name, rows in legs.items()}
    result["strategies_with_zero_executions"] = [name for name, rows in legs.items() if not rows]
    result["execution_failures"] = failures
    result["operationally_viable"] = not result["strategies_with_zero_executions"] and not failures
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cat", type=Path, required=True)
    parser.add_argument("--msft", type=Path, required=True)
    parser.add_argument("--jpm", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--capital", type=float, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capitals = args.capital or [500.0, 1000.0, 1500.0, 2000.0, 3000.0]
    if any(value <= 0 for value in capitals):
        raise ValueError("capital must be positive")
    result = {
        "schema_version": 1,
        "classification": "SMALL_ACCOUNT_FEASIBILITY_DIAGNOSTIC",
        "period": "2022-01-01/2024-12-31",
        "allocation": "four fixed 25% compartments, whole units, no leverage, no weight search",
        "capital_grid": {str(int(value)): audit(args.cat, args.msft, args.jpm, args.gold, value)
                         for value in capitals},
        "gold_execution": "SGLN.L GBp converted to GBP; GBP/account FX fixed 1:1; GBP1.25 per position change; 5bps adverse execution",
        "limitations": [
            "Fixed compartments are implementable but do not dynamically share idle cash.",
            "GBP/account FX history and the exact IBKR listing/commission are not yet modeled.",
            "Drawdown is closed-equity and gold is marked only at monthly decision points.",
            "Historical 2022-2024 is diagnostic, not a fresh holdout.",
        ],
        "inputs_sha256": {str(path): sha(path) for path in (args.cat, args.msft, args.jpm, args.gold)},
        "optimized": False,
        "paper_authorized": False,
        "live_authorized": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
