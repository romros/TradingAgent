#!/usr/bin/env python3
"""Independent replay of CAT candidate 0.168 (-DI turn-down, ATR exits)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wilder_sum(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result
    result[period] = sum(values[1:period + 1])
    for index in range(period + 1, len(values)):
        previous = result[index - 1]
        assert previous is not None
        result[index] = previous - previous / period + values[index]
    return result


def replay(source: Path, orders: Path, date_from: str, date_to: str) -> dict:
    raw = list(csv.reader(source.open(newline="", encoding="utf-8-sig")))
    dates = [row[0] for row in raw]
    opens = [float(row[2]) for row in raw]
    highs = [float(row[3]) for row in raw]
    lows = [float(row[4]) for row in raw]
    closes = [float(row[5]) for row in raw]
    tr, minus_dm = [highs[0] - lows[0]], [0.0]
    for index in range(1, len(raw)):
        tr.append(max(highs[index] - lows[index],
                      abs(highs[index] - closes[index - 1]),
                      abs(lows[index] - closes[index - 1])))
        up = highs[index] - highs[index - 1]
        down = lows[index - 1] - lows[index]
        minus_dm.append(down if down > up and down > 0 else 0.0)
    tr40, minus40 = _wilder_sum(tr, 40), _wilder_sum(minus_dm, 40)
    minus_di = [None if tr40[i] in {None, 0} else 100 * minus40[i] / tr40[i]
                for i in range(len(raw))]
    tr30 = _wilder_sum(tr, 30)
    atr30 = [None if value is None else value / 30 for value in tr30]

    simulated, position = [], None
    first_allowed_index = 100 if date_from == dates[0] else 0
    for index, day in enumerate(dates):
        if day < date_from:
            continue
        if day > date_to:
            break
        exited = exited_at_open = False
        if position is not None:
            stop, target = position["stop"], position["target"]
            kind = price = None
            if opens[index] <= stop:
                kind, price, exited_at_open = "SL", opens[index], True
            elif opens[index] >= target:
                kind, price, exited_at_open = "PT", opens[index], True
            elif lows[index] <= stop:  # conservative when both touch intrabar
                kind, price = "SL", stop
            elif highs[index] >= target:
                kind, price = "PT", target
            if kind:
                simulated.append({**position, "close_date": day,
                                  "close_type": kind, "close_price": price})
                position, exited = None, True
        # SQ evaluates the entry after processing an exit and can therefore
        # reopen at that same bar's open when the signal is active.
        if (position is None and index >= max(4, first_allowed_index)
                and (not exited or exited_at_open)):
            values = [minus_di[index - shift] for shift in (2, 3, 4)]
            signal = (all(value is not None for value in values)
                      and values[0] < values[1] and values[1] >= values[2])
            if signal:
                atr = atr30[index - 1]
                if atr is None:
                    continue
                position = {"open_date": day, "open_price": opens[index],
                            "stop": opens[index] - 2.5 * atr,
                            "target": opens[index] + 2.1 * atr}
                # D1 cannot reveal intrabar order; SQ's pessimistic precision
                # applies the stop first when an entry bar touches an exit.
                if lows[index] <= position["stop"]:
                    simulated.append({**position, "close_date": day,
                                      "close_type": "SL",
                                      "close_price": position["stop"]})
                    position = None
                elif highs[index] >= position["target"]:
                    simulated.append({**position, "close_date": day,
                                      "close_type": "PT",
                                      "close_price": position["target"]})
                    position = None
    if position is not None:
        end_index = dates.index(date_to)
        simulated.append({**position, "close_date": date_to,
                          "close_type": "EndTest", "close_price": closes[end_index]})

    with orders.open(newline="", encoding="utf-8-sig") as stream:
        observed = list(csv.DictReader(stream, delimiter=";"))
    mismatches = []
    if len(simulated) != len(observed):
        mismatches.append({"trade_count": [len(simulated), len(observed)]})
    for index, (left, right) in enumerate(zip(simulated, observed), 1):
        expected = (left["open_date"], left["close_date"], left["close_type"])
        actual = (right["Open time"][:10], right["Close time"][:10], right["Close type"])
        open_error = abs(left["open_price"] - float(right["Open price"]))
        close_error = abs(left["close_price"] - float(right["Close price"]))
        if expected != actual or open_error > .001 or close_error > .06:
            mismatches.append({"trade": index, "expected": expected, "actual": actual,
                               "open_error": open_error, "close_error": close_error})
    return {
        "schema_version": 1,
        "decision": "PASS_INDEPENDENT_TRADE_PARITY" if not mismatches else "REJECT_PARITY",
        "candidate_id": "Strategy 0.168", "source_sha256": _sha(source),
        "orders_sha256": _sha(orders), "date_from": date_from, "date_to": date_to,
        "signal": "Wilder -DI(40) shift2 crosses below its shift3 value",
        "execution": "market open; SL=2.5*ATR30; PT=2.1*ATR30; SQ exit-then-entry ordering",
        "simulated_trades": len(simulated), "sq_trades": len(observed),
        "mismatches": mismatches, "oos_accessed": date_from >= "2024.01.01",
        "holdout_accessed": date_from >= "2025.01.01",
        "paper_authorized": False, "live_authorized": False}


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
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["decision"].startswith("PASS") else 1)


if __name__ == "__main__":
    main()
