#!/usr/bin/env python3
"""Frozen deterministic neighborhood for CAT -DI turn-down candidate 0.168."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

PERIODS_ADX = (30, 40, 50)
PERIODS_ATR = (20, 30, 40)
TARGET_ATR = (1.8, 2.1, 2.4)
STOP_ATR = (2.2, 2.5, 2.8)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wilder(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result
    result[period] = sum(values[1:period + 1])
    for index in range(period + 1, len(values)):
        previous = result[index - 1]
        assert previous is not None
        result[index] = previous - previous / period + values[index]
    return result


def _pf(pnls: list[float]) -> float:
    wins, losses = sum(max(x, 0) for x in pnls), -sum(min(x, 0) for x in pnls)
    return wins / losses if losses else (999.0 if wins else 0.0)


def _drawdown(pnls: list[float]) -> float:
    equity = peak = 0.0
    maximum = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def run(source: Path, output: Path) -> dict:
    rows = list(csv.reader(source.open(newline="", encoding="utf-8-sig")))
    dates = [row[0] for row in rows]
    opens = [float(row[2]) for row in rows]
    highs = [float(row[3]) for row in rows]
    lows = [float(row[4]) for row in rows]
    closes = [float(row[5]) for row in rows]
    tr, minus_dm = [highs[0] - lows[0]], [0.0]
    for index in range(1, len(rows)):
        tr.append(max(highs[index] - lows[index],
                      abs(highs[index] - closes[index - 1]),
                      abs(lows[index] - closes[index - 1])))
        up, down = highs[index] - highs[index - 1], lows[index - 1] - lows[index]
        minus_dm.append(down if down > up and down > 0 else 0.0)
    indicators = {}
    for period in set(PERIODS_ADX + PERIODS_ATR):
        smoothed_tr = _wilder(tr, period)
        indicators[("atr", period)] = [None if x is None else x / period for x in smoothed_tr]
        smoothed_minus = _wilder(minus_dm, period)
        indicators[("mdi", period)] = [
            None if smoothed_tr[i] in {None, 0} else 100 * smoothed_minus[i] / smoothed_tr[i]
            for i in range(len(rows))]

    periods = {"train": ("2017.05.11", "2021.12.30"),
               "validation": ("2022.01.03", "2023.12.29")}
    results = []
    for adx_period, atr_period, target_multiple, stop_multiple in itertools.product(
            PERIODS_ADX, PERIODS_ATR, TARGET_ATR, STOP_ATR):
        row = {"adx_period": adx_period, "atr_period": atr_period,
               "target_atr": target_multiple, "stop_atr": stop_multiple}
        for sample, (date_from, date_to) in periods.items():
            mdi, atr = indicators[("mdi", adx_period)], indicators[("atr", atr_period)]
            gross_trades, position = [], None
            for index, day in enumerate(dates):
                if day < date_from:
                    continue
                if day > date_to:
                    break
                exited = exited_at_open = False
                if position:
                    stop, target, entry = position
                    if opens[index] <= stop:
                        gross_trades.append((entry, opens[index])); position = None; exited = exited_at_open = True
                    elif opens[index] >= target:
                        gross_trades.append((entry, opens[index])); position = None; exited = exited_at_open = True
                    elif lows[index] <= stop:
                        gross_trades.append((entry, stop)); position = None; exited = True
                    elif highs[index] >= target:
                        gross_trades.append((entry, target)); position = None; exited = True
                if position is None and index >= 4 and (not exited or exited_at_open):
                    values = [mdi[index - shift] for shift in (2, 3, 4)]
                    if (all(value is not None for value in values)
                            and values[0] < values[1] and values[1] >= values[2]
                            and atr[index - 1] is not None):
                        entry = opens[index]
                        position = (entry - stop_multiple * atr[index - 1],
                                    entry + target_multiple * atr[index - 1], entry)
            if position:
                end = dates.index(date_to)
                gross_trades.append((position[2], closes[end]))
            # Reproduce the existing small-account stress contract: all
            # available realized equity, whole shares, 10 bps adverse each
            # side and fixed-plan commission on both orders.
            equity, net = 1000.0, []
            for raw_entry, raw_exit in gross_trades:
                entry, exit_price = raw_entry * 1.001, raw_exit * .999
                shares = int(equity // entry)
                if shares < 1:
                    continue
                fee = max(1.0, .005 * shares)
                pnl = shares * (exit_price - entry) - 2 * fee
                equity += pnl
                net.append(pnl)
            row[sample] = {"trades": len(net), "net_pnl_usd": round(sum(net), 6),
                           "profit_factor": round(_pf(net), 6),
                           "expectancy_usd": round(sum(net) / len(net), 6) if net else None,
                           "drawdown_usd": round(_drawdown(net), 6)}
        results.append(row)
    passing = [row for row in results if row["train"]["trades"] >= 35
               and row["train"]["profit_factor"] >= 1.15
               and row["validation"]["trades"] >= 24
               and row["validation"]["profit_factor"] >= 1.10
               and row["validation"]["net_pnl_usd"] > 0]
    center = next(row for row in results if (row["adx_period"], row["atr_period"],
                  row["target_atr"], row["stop_atr"]) == (40, 30, 2.1, 2.5))
    result = {"schema_version": 1, "decision": "PASS_NEIGHBORHOOD_DENSITY" if
              len(passing) / len(results) >= .5 else "REJECT_NEIGHBORHOOD_DENSITY",
              "source_path": str(source.resolve()), "source_sha256": _sha(source),
              "grid_frozen_before_execution": True, "grid_points": len(results),
              "parameters": {"adx_period": PERIODS_ADX, "atr_period": PERIODS_ATR,
                  "target_atr": TARGET_ATR, "stop_atr": STOP_ATR},
              "cost_model": "IBKR stress: whole shares/all equity, 10bps adverse per side, max($1,$0.005/share) per order",
              "passing_points": len(passing), "passing_ratio": round(len(passing) / len(results), 6),
              "center": center, "results": results, "oos_accessed": False,
              "holdout_accessed": False, "paper_authorized": False, "live_authorized": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.source, args.output)
    print(json.dumps({key: result[key] for key in ("decision", "grid_points",
        "passing_points", "passing_ratio", "center", "oos_accessed", "holdout_accessed")}, indent=2))


if __name__ == "__main__":
    main()
