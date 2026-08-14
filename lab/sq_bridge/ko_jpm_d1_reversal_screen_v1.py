#!/usr/bin/env python3
"""Evaluate the hash-locked KO/JPM D1 reversal preregistration."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from cat_adx_pullback_parity_v2 import _wilder_sum
from ibkr_equity_small_account_audit_v2 import simulate

HERE = Path(__file__).resolve().parent
DEFAULT_PREREG = HERE / "ko_jpm_d1_reversal_preregistration_v1.json"
DEFAULT_LOCK = HERE / "ko_jpm_d1_reversal_preregistration_v1.lock.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen(prereg_path: Path, lock_path: Path) -> tuple[dict, str]:
    lock = json.loads(lock_path.read_text())
    actual = sha256(prereg_path)
    if lock.get("preregistration_sha256") != actual:
        raise ValueError("preregistration hash mismatch: refuse performance evaluation")
    prereg = json.loads(prereg_path.read_text())
    if prereg.get("status") != "FROZEN_BEFORE_PERFORMANCE":
        raise ValueError("preregistration is not frozen")
    return prereg, actual


def load_rows(path: Path) -> list[dict]:
    if not path.name.endswith("_2017_2024.csv") or "2025" in path.name:
        raise ValueError("input must end _2017_2024.csv and must not mention 2025")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        raw = list(csv.reader(stream))
    rows = []
    for row in raw:
        if not row or row[0].lower() == "date":
            continue
        date = row[0].replace(".", "-")
        datetime.strptime(date, "%Y-%m-%d")
        # canonical header format date,open,high,low,close,...; SQ format has time column
        offset = 2 if len(row) > 1 and ":" in row[1] else 1
        rows.append({"date": date, "open": float(row[offset]), "high": float(row[offset + 1]),
                     "low": float(row[offset + 2]), "close": float(row[offset + 3])})
    if not rows or any(row["date"] > "2024-12-31" for row in rows):
        raise ValueError("empty source or 2025 holdout leakage")
    if any(right["date"] <= left["date"] for left, right in zip(rows, rows[1:])):
        raise ValueError("dates must be strictly increasing")
    return rows


def indicators(rows: list[dict]) -> tuple[list[float | None], list[float | None]]:
    closes = [row["close"] for row in rows]
    highs = [row["high"] for row in rows]
    lows = [row["low"] for row in rows]
    tr = [highs[0] - lows[0]]
    for i in range(1, len(rows)):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                      abs(lows[i] - closes[i - 1])))
    atr = [None if value is None else value / 20 for value in _wilder_sum(tr, 20)]
    sma = [None] * len(rows)
    running = 0.0
    for i, close in enumerate(closes):
        running += close
        if i >= 200:
            running -= closes[i - 200]
        if i >= 199:
            sma[i] = running / 200
    return atr, sma


def orders_for(rows: list[dict], variant: dict, date_from: str, date_to: str) -> list[dict]:
    atr, sma = indicators(rows)
    eligible = [i for i, row in enumerate(rows) if date_from <= row["date"] <= date_to]
    if not eligible:
        return []
    orders, position = [], None
    last_index = eligible[-1]
    for i in eligible:
        row = rows[i]
        can_enter_at_open = position is None
        if position is not None:
            position["sessions"] += 1
            kind = price = None
            if row["open"] <= position["stop"]:
                kind, price = "SL", row["open"]
                can_enter_at_open = True
            elif position["target"] is not None and row["open"] >= position["target"]:
                kind, price = "PT", row["open"]
                can_enter_at_open = True
            elif row["low"] <= position["stop"]:
                kind, price = "SL", position["stop"]
            elif position["target"] is not None and row["high"] >= position["target"]:
                kind, price = "PT", position["target"]
            elif position["sessions"] >= variant["maximum_holding_sessions"]:
                kind, price = "Time", row["close"]
            if kind:
                position.update(close_time=datetime.strptime(row["date"], "%Y-%m-%d"),
                                close_price=price, close_type=kind)
                orders.append(position)
                position = None
        # Signal at close i; entry is next session, hence evaluate i-1 here.
        signal_index = i - 1
        lookback = variant["lookback_days"]
        if position is None and can_enter_at_open and signal_index >= max(219, lookback):
            signal_atr = atr[signal_index]
            trend = (sma[signal_index] is not None and sma[signal_index - 20] is not None
                     and rows[signal_index]["close"] > sma[signal_index]
                     and sma[signal_index] > sma[signal_index - 20])
            shock = (signal_atr is not None and rows[signal_index]["close"]
                     - rows[signal_index - lookback]["close"] <= -variant["shock_atr"] * signal_atr)
            if trend and shock:
                entry = row["open"]
                position = {
                    "open_time": datetime.strptime(row["date"], "%Y-%m-%d"),
                    "open_price": entry, "stop": entry - variant["stop_atr"] * signal_atr,
                    "target": (None if variant["target_atr"] is None else
                               entry + variant["target_atr"] * signal_atr),
                    "sessions": 1, "sq_pnl_one_share": 0.0, "mae": None, "mfe": None,
                }
                # Entry-bar ambiguity is resolved pessimistically, exactly as
                # preregistered: the stop is evaluated before the target.
                if row["low"] <= position["stop"]:
                    position.update(close_time=position["open_time"], close_price=position["stop"],
                                    close_type="SL")
                    orders.append(position)
                    position = None
                elif position["target"] is not None and row["high"] >= position["target"]:
                    position.update(close_time=position["open_time"], close_price=position["target"],
                                    close_type="PT")
                    orders.append(position)
                    position = None
    if position is not None:
        row = rows[last_index]
        position.update(close_time=datetime.strptime(row["date"], "%Y-%m-%d"),
                        close_price=row["close"], close_type="EndTest")
        orders.append(position)
    return orders


def _passes(period: dict, gates: dict, capital: str, name: str) -> bool:
    minimum = gates["minimum_validation_trades"] if name == "validation" else gates["minimum_oos_trades"]
    stress = period["results"].get(capital, {}).get("stress", {})
    pf = stress.get("profit_factor")
    return (period["trades"] >= minimum and pf is not None
            and pf >= gates["minimum_stress_profit_factor_each_validation_and_oos"]
            and stress["return_pct"] > gates["minimum_stress_net_return_pct_each_validation_and_oos"]
            and stress["maximum_drawdown_pct_close_to_close"] <= gates["maximum_stress_drawdown_pct_each_validation_and_oos"])


def evaluate_asset(asset: str, path: Path, prereg: dict) -> dict:
    if asset not in prereg["assets"]:
        raise ValueError(f"asset outside frozen universe: {asset}")
    rows = load_rows(path)
    periods = prereg["temporal_contract"]
    capitals = prereg["cost_and_sizing_contract"]["capitals_usd"]
    gates = prereg["preregistered_gates"]
    variants = {}
    for variant in prereg["variants"]:
        result_periods = {}
        for name in ("train", "validation", "oos"):
            orders = orders_for(rows, variant, *periods[name])
            results = {}
            for capital in capitals:
                try:
                    results[str(capital)] = {plan: simulate(orders, initial_capital=capital, plan=plan)
                                             for plan in ("tiered", "fixed", "stress")}
                except ValueError as exc:
                    results[str(capital)] = {"not_executable": str(exc)}
            result_periods[name] = {"trades": len(orders), "results": results}
        gate_capital = str(gates["must_pass_capital_usd"])
        pass_validation = _passes(result_periods["validation"], gates, gate_capital, "validation")
        pass_oos = _passes(result_periods["oos"], gates, gate_capital, "oos")
        enough_combined = (result_periods["validation"]["trades"] + result_periods["oos"]["trades"]
                           >= gates["minimum_combined_validation_oos_trades"])
        variants[variant["id"]] = {"definition": variant, "periods": result_periods,
                                    "asset_gate_pass": pass_validation and pass_oos and enough_combined}
    return {"source": str(path.resolve()), "source_sha256": sha256(path),
            "first_date": rows[0]["date"], "last_date": rows[-1]["date"], "variants": variants}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--asset", action="append", required=True, help="KO=/path/KO_2017_2024.csv")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prereg, prereg_hash = load_frozen(args.preregistration, args.lock)
    supplied = {}
    for spec in args.asset:
        asset, separator, path = spec.partition("=")
        if not separator:
            raise SystemExit("--asset requires ASSET=PATH")
        supplied[asset] = Path(path)
    if set(supplied) != set(prereg["assets"]):
        raise SystemExit("all and only frozen assets KO,JPM must be supplied")
    assets = {asset: evaluate_asset(asset, supplied[asset], prereg) for asset in prereg["assets"]}
    family_pass = [variant["id"] for variant in prereg["variants"] if all(
        assets[asset]["variants"][variant["id"]]["asset_gate_pass"] for asset in prereg["assets"])]
    report = {"schema_version": 1, "stage": "FROZEN_KO_JPM_D1_REVERSAL_SCREEN",
              "preregistration_sha256": prereg_hash, "assets": assets,
              "cross_asset_passing_variants": family_pass,
              "holdout_2025_accessed": False, "optimized": False,
              "paper_authorized": False, "live_authorized": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
