#!/usr/bin/env python3
"""Frozen cross-asset screen for CAT Strategy 0.168 through 2024 only.

This is a transfer test, not an optimiser.  It deliberately exposes no strategy
parameters on the command line and refuses inputs whose name does not explicitly
declare a 2024 endpoint.  The 2025 holdout must remain outside this process.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from cat_adx_pullback_parity_v2 import _wilder_sum
from ibkr_equity_small_account_audit_v2 import simulate


PERIODS = {
    "train": ("2017.01.01", "2021.12.31"),
    "validation": ("2022.01.01", "2023.12.31"),
    "oos": ("2024.01.01", "2024.12.31"),
}
FROZEN = {
    "direction": "long",
    "signal": "Wilder -DI(40) shift2 crosses below shift3; shift3 >= shift4",
    "atr_period": 30,
    "stop_atr": 2.5,
    "target_atr": 2.1,
    "entry": "next market open",
    "intrabar_policy": "stop_before_target",
    "exit_then_entry": "same-bar reopen only after an open exit",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_preholdout(path: Path) -> list[dict]:
    # The filename is the data-boundary receipt.  Reject before reading bytes so
    # an accidental 2017_2025 canonical file cannot leak the sealed holdout.
    if "2024" not in path.name or "2025" in path.name:
        raise ValueError("source filename must declare a through-2024 dataset and must not mention 2025")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.reader(stream))
    parsed = []
    for row in rows:
        if not row:
            continue
        try:
            datetime.strptime(row[0], "%Y.%m.%d")
            parsed.append({"date": row[0], "open": float(row[2]), "high": float(row[3]),
                           "low": float(row[4]), "close": float(row[5])})
        except (ValueError, IndexError):
            # Also accept canonical header CSV: date,open,high,low,close,...
            if row[0].lower() == "date":
                continue
            date = row[0].replace("-", ".")
            datetime.strptime(date, "%Y.%m.%d")
            parsed.append({"date": date, "open": float(row[1]), "high": float(row[2]),
                           "low": float(row[3]), "close": float(row[4])})
    if not parsed or any(row["date"] >= "2025.01.01" for row in parsed):
        raise ValueError("empty data or holdout leakage: all rows must end by 2024-12-31")
    if any(right["date"] <= left["date"] for left, right in zip(parsed, parsed[1:])):
        raise ValueError("dates must be strictly increasing")
    return parsed


def frozen_orders(rows: list[dict], date_from: str, date_to: str) -> list[dict]:
    highs = [row["high"] for row in rows]
    lows = [row["low"] for row in rows]
    closes = [row["close"] for row in rows]
    true_range, minus_dm = [highs[0] - lows[0]], [0.0]
    for index in range(1, len(rows)):
        true_range.append(max(highs[index] - lows[index],
                              abs(highs[index] - closes[index - 1]),
                              abs(lows[index] - closes[index - 1])))
        up = highs[index] - highs[index - 1]
        down = lows[index - 1] - lows[index]
        minus_dm.append(down if down > up and down > 0 else 0.0)
    tr40, dm40 = _wilder_sum(true_range, 40), _wilder_sum(minus_dm, 40)
    minus_di = [None if tr40[i] in {None, 0} else 100 * dm40[i] / tr40[i]
                for i in range(len(rows))]
    atr30 = [None if value is None else value / 30
             for value in _wilder_sum(true_range, 30)]

    orders: list[dict] = []
    position = None
    eligible = [i for i, row in enumerate(rows) if date_from <= row["date"] <= date_to]
    if not eligible:
        return orders
    last_index = eligible[-1]
    for index in eligible:
        row = rows[index]
        exited = exited_at_open = False
        if position is not None:
            kind = price = None
            if row["open"] <= position["stop"]:
                kind, price, exited_at_open = "SL", row["open"], True
            elif row["open"] >= position["target"]:
                kind, price, exited_at_open = "PT", row["open"], True
            elif row["low"] <= position["stop"]:
                kind, price = "SL", position["stop"]
            elif row["high"] >= position["target"]:
                kind, price = "PT", position["target"]
            if kind:
                position.update(close_time=datetime.strptime(row["date"], "%Y.%m.%d"),
                                close_price=price, close_type=kind)
                orders.append(position)
                position, exited = None, True
        if position is None and index >= 4 and (not exited or exited_at_open):
            values = [minus_di[index - shift] for shift in (2, 3, 4)]
            signal = all(value is not None for value in values) and values[0] < values[1] and values[1] >= values[2]
            atr = atr30[index - 1]
            if signal and atr is not None:
                position = {
                    "open_time": datetime.strptime(row["date"], "%Y.%m.%d"),
                    "open_price": row["open"], "stop": row["open"] - 2.5 * atr,
                    "target": row["open"] + 2.1 * atr, "sq_pnl_one_share": 0.0,
                    "mae": None, "mfe": None,
                }
                if row["low"] <= position["stop"]:
                    position.update(close_time=position["open_time"], close_price=position["stop"], close_type="SL")
                    orders.append(position)
                    position = None
                elif row["high"] >= position["target"]:
                    position.update(close_time=position["open_time"], close_price=position["target"], close_type="PT")
                    orders.append(position)
                    position = None
    if position is not None:
        row = rows[last_index]
        position.update(close_time=datetime.strptime(row["date"], "%Y.%m.%d"),
                        close_price=row["close"], close_type="EndTest")
        orders.append(position)
    return orders


def screen(asset: str, source: Path, capitals: list[float]) -> dict:
    rows = _load_preholdout(source)
    periods = {}
    for name, (date_from, date_to) in PERIODS.items():
        orders = frozen_orders(rows, date_from, date_to)
        periods[name] = {
            "date_from": date_from, "date_to": date_to,
            "results": {str(int(capital)): {plan: simulate(orders, initial_capital=capital, plan=plan)
                                             for plan in ("tiered", "fixed", "stress")}
                        for capital in capitals} if orders else {},
            "trades": len(orders),
        }
    return {
        "asset": asset, "source_path": str(source.resolve()), "source_sha256": _sha(source),
        "first_date": rows[0]["date"], "last_date": rows[-1]["date"],
        "strategy": FROZEN, "periods": periods,
        "optimized": False, "holdout_2025_accessed": False,
        "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", action="append", required=True,
                        help="ASSET=/path/to/canonical_through_2024.csv")
    parser.add_argument("--capital", action="append", type=float, default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    capitals = args.capital or [1000.0]
    if any(capital <= 0 for capital in capitals):
        raise SystemExit("capital must be positive")
    assets = {}
    for spec in args.asset:
        name, separator, raw_path = spec.partition("=")
        if not separator or not name or not raw_path:
            raise SystemExit("--asset must have ASSET=PATH form")
        assets[name] = screen(name, Path(raw_path), capitals)
    report = {
        "schema_version": 1, "stage": "CAT_0168_FROZEN_CROSS_ASSET_TRANSFER",
        "period_contract": PERIODS, "assets": assets, "optimized": False,
        "holdout_2025_accessed": False, "paper_authorized": False, "live_authorized": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
