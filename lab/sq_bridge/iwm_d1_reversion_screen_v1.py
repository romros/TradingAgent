#!/usr/bin/env python3
"""Frozen train/validation screen for the IWM D1 small-cap reversal family."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "iwm_d1_reversion_preregistration_v1.json"
LOCK = HERE / "iwm_d1_reversion_preregistration_v1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    if "2025" in path.name or "2026" in path.name:
        raise ValueError("FUTURE_HOLDOUT_FILENAME_SEALED")
    rows = []
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        for fields in reader:
            if not fields:
                continue
            if fields[0].lower() in {"date", "time", "datetime"}:
                continue
            try:
                day = dt.datetime.strptime(fields[0][:10], "%Y.%m.%d").date()
            except ValueError:
                day = dt.date.fromisoformat(fields[0][:10])
            if day.year >= 2025:
                raise ValueError("FUTURE_HOLDOUT_ROW_SEALED")
            # Canonical SQ D1 is Date,Time,Open,High,Low,Close,Volume.
            # A conventional OHLC headerless fixture can omit the Time column.
            offset = 1 if len(fields) >= 7 else 0
            rows.append({"date": day, "open": float(fields[1 + offset]),
                         "close": float(fields[4 + offset])})
    return rows


def rsi_wilder(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, len(values))]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, len(values))]
    gain = sum(gains[:period]) / period
    loss = sum(losses[:period]) / period
    out[period] = 100.0 if loss == 0 else 100.0 - 100.0 / (1.0 + gain / loss)
    for i in range(period + 1, len(values)):
        gain = (gain * (period - 1) + gains[i - 1]) / period
        loss = (loss * (period - 1) + losses[i - 1]) / period
        out[i] = 100.0 if loss == 0 else 100.0 - 100.0 / (1.0 + gain / loss)
    return out


def trades(rows: list[dict], variant: tuple[int, int, int, int, int]) -> list[dict]:
    period, threshold, exit_sma, trend_sma, max_hold = variant
    closes = [row["close"] for row in rows]
    rsi = rsi_wilder(closes, period)
    result = []
    entry = None
    start = max(period, exit_sma, trend_sma) - 1
    for i in range(start, len(rows) - 1):
        if entry is None:
            trend = sum(closes[i - trend_sma + 1:i + 1]) / trend_sma
            if closes[i] > trend and rsi[i] is not None and rsi[i] < threshold:
                entry = {"index": i + 1, "price": rows[i + 1]["open"]}
        elif i >= entry["index"]:
            exit_mean = sum(closes[i - exit_sma + 1:i + 1]) / exit_sma
            held = i - entry["index"] + 1
            if closes[i] > exit_mean or held >= max_hold:
                result.append({"entry": rows[entry["index"]]["date"],
                               "exit": rows[i + 1]["date"],
                               "return": rows[i + 1]["open"] / entry["price"] - 1.0,
                               "holding_sessions": held})
                entry = None
    return result


def metrics(rows: list[dict]) -> dict:
    returns = [row["return"] for row in rows]
    if not returns:
        return {"trades": 0, "mean_return": None, "profit_factor": None,
                "t_stat": None, "total_return": 0.0, "max_drawdown": 0.0}
    mean = sum(returns) / len(returns)
    sd = math.sqrt(sum((value - mean) ** 2 for value in returns) /
                   (len(returns) - 1)) if len(returns) > 1 else 0.0
    gains = sum(value for value in returns if value > 0)
    losses = -sum(value for value in returns if value < 0)
    equity = peak = 1.0
    drawdown = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        drawdown = max(drawdown, 1.0 - equity / peak)
    return {"trades": len(returns), "mean_return": mean,
            "profit_factor": gains / losses if losses else None,
            "t_stat": mean / (sd / math.sqrt(len(returns))) if sd else None,
            "total_return": equity - 1.0, "max_drawdown": drawdown,
            "average_holding_sessions": sum(row["holding_sessions"] for row in rows) / len(rows)}


def period(rows: list[dict], start: dt.date, end: dt.date) -> list[dict]:
    return [row for row in rows if start <= row["entry"] and row["exit"] <= end]


def variant_id(value: tuple[int, int, int, int, int]) -> str:
    return "rsi%d_b%d_x%d_t%d_h%d" % value


def immediate_neighbours(center, variants):
    return [value for value in variants if sum(a != b for a, b in zip(center, value)) == 1]


def screen(source: Path, output: Path) -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    if sha(SPEC) != lock["preregistration_sha256"]:
        raise ValueError("PREREGISTRATION_LOCK_MISMATCH")
    rows = load(source)
    grid = spec["variants"]
    variants = [(r, b, x, t, h) for r in grid["rsi_period"]
                for b in grid["entry_below"] for x in grid["exit_sma"]
                for t in grid["trend_sma"] for h in grid["maximum_holding_sessions"]]
    bounds = {name: tuple(map(dt.date.fromisoformat, dates))
              for name, dates in spec["periods"].items() if isinstance(dates, list)}
    all_trades = {value: trades(rows, value) for value in variants}
    train = {value: metrics(period(all_trades[value], *bounds["train"])) for value in variants}
    gate = spec["train_selection_gate"]
    eligible = []
    for value in variants:
        neighbours = immediate_neighbours(value, variants)
        positive = [train[item] for item in neighbours
                    if train[item]["trades"] >= gate["minimum_trades"]
                    and (train[item]["profit_factor"] or 0) >= gate["minimum_profit_factor"]]
        central = train[value]
        if (central["trades"] >= gate["minimum_trades"]
                and (central["profit_factor"] or 0) >= gate["minimum_profit_factor"]
                and len(positive) >= gate["minimum_positive_immediate_neighbours"]):
            neighbourhood = sorted(row["t_stat"] or -999.0 for row in positive)
            eligible.append((neighbourhood[len(neighbourhood) // 2],
                             central["t_stat"] or -999.0, variant_id(value), value,
                             len(positive)))
    selected = max(eligible, default=None)
    report = {"schema_version": 1, "preregistration_sha256": sha(SPEC),
              "source_sha256": sha(source), "variant_count": len(variants),
              "holdout_2025_plus_accessed": False,
              "train": {variant_id(value): train[value] for value in variants},
              "train_eligible_count": len(eligible), "selected": None,
              "decision": "REJECT_NO_STABLE_TRAIN_REGION",
              "oos_2024_accessed": False, "paper_authorized": False,
              "live_authorized": False}
    if selected:
        _, _, identifier, value, neighbour_count = selected
        validation_rows = period(all_trades[value], *bounds["validation"])
        validation = metrics(validation_rows)
        vg = spec["validation_release_gate"]
        passes = (validation["trades"] >= vg["minimum_trades"]
                  and (validation["profit_factor"] or 0) >= vg["minimum_profit_factor"]
                  and (validation["mean_return"] or 0) > vg["minimum_mean_return"]
                  and validation["max_drawdown"] <= vg["maximum_drawdown"])
        report["selected"] = {"id": identifier, "parameters": value,
                              "positive_immediate_neighbours": neighbour_count,
                              "train": train[value], "validation": validation}
        report["decision"] = ("PASS_VALIDATION_FREEZE_BEFORE_OOS" if passes
                              else "REJECT_VALIDATION")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = screen(args.source, args.output)
    print(json.dumps({"decision": result["decision"],
                      "selected": result["selected"]}, indent=2))


if __name__ == "__main__":
    main()
