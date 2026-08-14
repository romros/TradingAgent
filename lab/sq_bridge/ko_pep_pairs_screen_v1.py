#!/usr/bin/env python3
"""Frozen staged KO/PEP D1 pairs screen; 2024 remains sealed unless validation passes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
PREREG = HERE / "ko_pep_pairs_preregistration_v1.json"
FROZEN_SHA256 = "6f0a55be89ad35c03b631e156714e024416bce872d5ccb170abcf3493076edf0"


@dataclass(frozen=True)
class Bar:
    day: date
    open: float
    close: float


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_bars(path: Path, maximum_read_date: date = date(2024, 12, 31)) -> dict[date, Bar]:
    if "2025" in path.name:
        raise ValueError("2025 is sealed by filename")
    result: dict[date, Bar] = {}
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            day = date.fromisoformat(row["date"])
            if day >= date(2025, 1, 1):
                raise ValueError("2025 is sealed by row date")
            if day > maximum_read_date:
                continue
            result[day] = Bar(day, float(row["open"]), float(row["close"]))
    return result


def common_series(ko: dict[date, Bar], pep: dict[date, Bar]) -> list[dict[str, object]]:
    rows = []
    history: list[tuple[float, float]] = []
    for day in sorted(set(ko) & set(pep)):
        x, y = math.log(pep[day].close), math.log(ko[day].close)
        history.append((x, y))
        beta = z = None
        if len(history) >= 60:
            window = history[-60:]
            mx = sum(v[0] for v in window) / 60
            my = sum(v[1] for v in window) / 60
            denominator = sum((v[0] - mx) ** 2 for v in window)
            if denominator > 0:
                beta = sum((a - mx) * (b - my) for a, b in window) / denominator
                spreads = [b - beta * a for a, b in window]
                mean = sum(spreads) / 60
                variance = sum((v - mean) ** 2 for v in spreads) / 59
                if variance > 0:
                    z = (spreads[-1] - mean) / math.sqrt(variance)
        rows.append({"day": day, "ko": ko[day], "pep": pep[day], "beta": beta, "z": z})
    return rows


def simulate(rows: list[dict[str, object]], start: date, end: date, capital: float = 1000.0) -> dict[str, object]:
    trades: list[dict[str, object]] = []
    position = None
    pending_entry = None
    pending_exit = None
    held = 0
    equity = capital
    peak = capital
    max_dd = 0.0
    previous = None

    for row in rows:
        day = row["day"]
        if day < start:
            previous = row
            continue
        if day > end:
            break

        exited_today = False
        if position and pending_exit:
            ko_exit, pep_exit = row["ko"].open, row["pep"].open
            days = max(1, (day - position["entry_day"]).days)
            if position["direction"] == -1:  # short KO, long PEP
                gross = position["ko_qty"] * (position["ko_entry"] - ko_exit) + position["pep_qty"] * (pep_exit - position["pep_entry"])
                short_value = position["ko_qty"] * position["ko_entry"]
            else:
                gross = position["ko_qty"] * (ko_exit - position["ko_entry"]) + position["pep_qty"] * (position["pep_entry"] - pep_exit)
                short_value = position["pep_qty"] * position["pep_entry"]
            exit_notional = position["ko_qty"] * ko_exit + position["pep_qty"] * pep_exit
            borrow = short_value * 0.05 * days / 365.0
            costs = position["entry_cost"] + 2.0 + 0.001 * exit_notional + borrow
            net = gross - costs
            equity += net
            trades.append({"entry": position["entry_day"].isoformat(), "exit": day.isoformat(), "direction": position["direction"], "gross": gross, "costs": costs, "net": net, "reason": pending_exit})
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak * 100 if peak else 0)
            position = None
            pending_exit = None
            exited_today = True

        if not position and not exited_today and pending_entry is not None:
            ko_open, pep_open = row["ko"].open, row["pep"].open
            leg_budget = equity / 2
            ko_qty, pep_qty = math.floor(leg_budget / ko_open), math.floor(leg_budget / pep_open)
            if ko_qty >= 1 and pep_qty >= 1:
                notional = ko_qty * ko_open + pep_qty * pep_open
                position = {"entry_day": day, "direction": pending_entry, "ko_entry": ko_open, "pep_entry": pep_open,
                            "ko_qty": ko_qty, "pep_qty": pep_qty, "entry_cost": 2.0 + 0.001 * notional}
                held = 0
            pending_entry = None

        if position:
            held += 1
            z = row["z"]
            if z is not None and abs(z) >= 3.5:
                pending_exit = "z_stop"
            elif z is not None and abs(z) <= 0.5:
                pending_exit = "mean_reversion"
            elif held >= 10:
                pending_exit = "time"
        elif row["z"] is not None and abs(row["z"]) >= 2.0:
            pending_entry = -1 if row["z"] > 0 else 1
        marked_equity = equity
        if position:
            ko_mark, pep_mark = row["ko"].close, row["pep"].close
            days = max(1, (day - position["entry_day"]).days)
            if position["direction"] == -1:
                gross_open = position["ko_qty"] * (position["ko_entry"] - ko_mark) + position["pep_qty"] * (pep_mark - position["pep_entry"])
                short_value = position["ko_qty"] * position["ko_entry"]
            else:
                gross_open = position["ko_qty"] * (ko_mark - position["ko_entry"]) + position["pep_qty"] * (position["pep_entry"] - pep_mark)
                short_value = position["pep_qty"] * position["pep_entry"]
            estimated_exit_cost = 2.0 + 0.001 * (position["ko_qty"] * ko_mark + position["pep_qty"] * pep_mark)
            marked_equity += gross_open - position["entry_cost"] - estimated_exit_cost - short_value * 0.05 * days / 365.0
        peak = max(peak, marked_equity)
        max_dd = max(max_dd, (peak - marked_equity) / peak * 100 if peak else 0)
        previous = row

    if position:
        # No invented fill beyond the period: mark an open trade but exclude it from closed-trade metrics.
        position = {**position, "unclosed_at_period_end": True}

    wins = sum(t["net"] for t in trades if t["net"] > 0)
    losses = -sum(t["net"] for t in trades if t["net"] < 0)
    halves = {"2022H1": 0.0, "2022H2": 0.0, "2023H1": 0.0, "2023H2": 0.0}
    for trade in trades:
        d = date.fromisoformat(trade["entry"])
        key = f"{d.year}H{1 if d.month <= 6 else 2}"
        if key in halves:
            halves[key] += trade["net"]
    return {
        "closed_pairs": len(trades),
        "net_pnl_usd": sum(t["net"] for t in trades),
        "net_return_pct": (equity / capital - 1) * 100,
        "profit_factor": wins / losses if losses else (1000000000.0 if wins else 0.0),
        "maximum_mark_to_market_drawdown_pct": max_dd,
        "positive_halves": sum(v > 0 for v in halves.values()),
        "half_pnl_usd": halves,
        "open_position_excluded": position is not None,
        "trades": trades
    }


def validation_passes(result: dict[str, object]) -> bool:
    return (result["closed_pairs"] >= 20 and result["profit_factor"] >= 1.15
            and result["net_return_pct"] > 0 and result["maximum_mark_to_market_drawdown_pct"] <= 20
            and result["positive_halves"] >= 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ko", type=Path, required=True)
    parser.add_argument("--pep", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if _sha256(PREREG) != FROZEN_SHA256:
        raise ValueError("preregistration changed after freeze")
    validation_ceiling = date(2023, 12, 31)
    ko, pep = load_bars(args.ko, validation_ceiling), load_bars(args.pep, validation_ceiling)
    rows = common_series(ko, pep)
    train = simulate(rows, date(2017, 11, 2), date(2021, 12, 31))
    validation = simulate(rows, date(2022, 1, 1), date(2023, 12, 31))
    passed = validation_passes(validation)
    oos = {"status": "SEALED"}
    if passed:
        full_rows = common_series(load_bars(args.ko), load_bars(args.pep))
        oos = simulate(full_rows, date(2024, 1, 1), date(2024, 12, 31))
    report = {
        "schema_version": 1, "campaign_id": "ibkr-ko-pep-d1-pairs-v1",
        "preregistration_sha256": FROZEN_SHA256,
        "common_sessions": len(rows), "train": train, "validation": validation,
        "validation_decision": "PASS_OPEN_OOS" if passed else "REJECT_KEEP_OOS_SEALED",
        "oos": oos
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"validation_decision": report["validation_decision"], "validation": validation, "oos": report["oos"]}, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
