#!/usr/bin/env python3
"""Independent OHLC replay of NFLX SQ candidate 0.4681."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atr(values: list[float], period: int) -> list[float]:
    """SQ-compatible progressive seed followed by Wilder smoothing."""
    result: list[float] = []
    for index, value in enumerate(values):
        if index == 0:
            result.append(value)
        elif index < period:
            result.append((result[-1] * index + value) / (index + 1))
        else:
            result.append((result[-1] * (period - 1) + value) / period)
    return result


def replay(source: Path, orders: Path, date_from: str, date_to: str) -> dict:
    raw = list(csv.reader(source.open(newline="", encoding="utf-8-sig")))
    dates = [row[0] for row in raw]
    opens = [float(row[2]) for row in raw]
    highs = [float(row[3]) for row in raw]
    lows = [float(row[4]) for row in raw]
    closes = [float(row[5]) for row in raw]
    tr = [highs[0] - lows[0]]
    for index in range(1, len(raw)):
        tr.append(max(highs[index] - lows[index],
                      abs(highs[index] - closes[index - 1]),
                      abs(lows[index] - closes[index - 1])))
    atr15, atr104 = atr(tr, 15), atr(tr, 104)

    trades: list[dict] = []
    position = None
    pending = None
    for index, day in enumerate(dates):
        if day < date_from:
            continue
        if day > date_to:
            break
        exited = False
        exited_at_open = False
        if position is not None:
            stop, target = position["stop"], position["target"]
            kind = price = None
            if opens[index] <= stop:
                kind, price = "SL", opens[index]
                exited_at_open = True
            elif opens[index] >= target:
                kind, price = "PT", opens[index]
                exited_at_open = True
            elif lows[index] <= stop:
                kind, price = "SL", stop
            elif highs[index] >= target:
                kind, price = "PT", target
            if kind:
                trades.append({**position, "close_date": day,
                               "close_type": kind, "close_price": price})
                position = None
                exited = True

        if position is not None or (exited and not exited_at_open):
            continue
        entered_today = False
        if pending is not None:
            pending["age"] += 1
            if pending["age"] >= 80:
                pending = None
            elif opens[index] >= pending["price"]:
                # A live order from the previous bar is filled by the opening
                # gap before OnBarUpdate gets a chance to replace it.
                entry = opens[index]
                distance = pending["atr15"]
                bracket_base = pending["price"]
                position = {
                    "open_date": day, "open_price": entry,
                    "stop": round(bracket_base - 2.5 * round(distance, 6), 3),
                    "target": round(bracket_base + 2.8 * round(distance, 6), 3),
                }
                pending = None
                entered_today = True
                if lows[index] <= position["stop"]:
                    trades.append({**position, "close_date": day,
                                   "close_type": "SL", "close_price": position["stop"]})
                    position = None
                elif highs[index] >= position["target"]:
                    trades.append({**position, "close_date": day,
                                   "close_type": "PT", "close_price": position["target"]})
                    position = None
        if entered_today:
            continue
        # The imported SQ market uses the campaign's explicit 100-bar warm-up.
        if index >= 100 and lows[index - 3] < highs[index - 1]:
            pending = {
                "price": round(max(highs[index - 10:index]) + 0.30 * atr104[index - 3], 3),
                "atr15": atr15[index - 1],
                "age": 0,
            }
        # A newly replaced BuyStop below the current open is invalid. A valid
        # new stop can still be reached during the remainder of this D1 bar.
        if pending is not None and pending["price"] < opens[index]:
            pending = None
            continue
        if pending is None or highs[index] < pending["price"]:
            continue
        entry = pending["price"]
        distance = pending["atr15"]
        position = {
            "open_date": day,
            "open_price": entry,
            "stop": round(entry - 2.5 * round(distance, 6), 3),
            "target": round(entry + 2.8 * round(distance, 6), 3),
        }
        pending = None
        if lows[index] <= position["stop"]:
            trades.append({**position, "close_date": day,
                           "close_type": "SL", "close_price": position["stop"]})
            position = None
        elif highs[index] >= position["target"]:
            trades.append({**position, "close_date": day,
                           "close_type": "PT", "close_price": position["target"]})
            position = None
    if position is not None:
        end_index = dates.index(date_to)
        trades.append({**position, "close_date": date_to,
                       "close_type": "EndTest", "close_price": closes[end_index]})

    with orders.open(newline="", encoding="utf-8-sig") as stream:
        observed = [row for row in csv.DictReader(stream, delimiter=";")
                    if row["Type"] == "Buy"]
    mismatches = []
    if len(trades) != len(observed):
        mismatches.append({"trade_count": [len(trades), len(observed)]})
    for number, (left, right) in enumerate(zip(trades, observed), 1):
        expected = (left["open_date"], left["close_date"], left["close_type"])
        actual = (right["Open time"][:10], right["Close time"][:10], right["Close type"])
        open_error = abs(left["open_price"] - float(right["Open price"]))
        close_error = abs(left["close_price"] - float(right["Close price"]))
        if expected != actual or open_error > .002 or close_error > .06:
            mismatches.append({"trade": number, "expected": expected,
                               "actual": actual, "open_error": open_error,
                               "close_error": close_error})
    return {
        "schema_version": 1,
        "decision": "PASS_INDEPENDENT_TRADE_PARITY" if not mismatches
                    else "REJECT_PARITY",
        "candidate_id": "Strategy 0.4681",
        "source_sha256": sha(source),
        "orders_sha256": sha(orders),
        "date_from": date_from,
        "date_to": date_to,
        "simulated_trades": len(trades),
        "sq_trades": len(observed),
        "mismatches": mismatches,
        "execution": "daily replaceable stop entry; fixed ATR15 bracket; pessimistic same-bar ordering",
        "holdout_2025_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = replay(args.source, args.orders, args.date_from, args.date_to)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "simulated_trades": result["simulated_trades"],
                      "sq_trades": result["sq_trades"],
                      "mismatch_count": len(result["mismatches"]),
                      "first_mismatches": result["mismatches"][:5]}, indent=2))
    raise SystemExit(0 if result["decision"].startswith("PASS") else 1)


if __name__ == "__main__":
    main()
