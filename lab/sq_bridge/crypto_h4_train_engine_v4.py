#!/usr/bin/env python3
"""Deterministic train-only engine for the sealed Alquimia crypto H4 rules."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


H4_SECONDS = 4 * 60 * 60
ATR_PERIOD = 14
SCENARIOS = ("base", "conservative", "stress")


@dataclass(frozen=True)
class Bars:
    timestamps: tuple[datetime, ...]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    segment: np.ndarray

    def __len__(self) -> int:
        return len(self.timestamps)


@dataclass(frozen=True)
class Trade:
    side: int
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    gross_return: float
    holding_bars: int
    exit_reason: str
    exit_year: int


def _timestamp(date: str, clock: str) -> datetime:
    return datetime.strptime(f"{date},{clock}", "%Y.%m.%d,%H:%M").replace(
        tzinfo=timezone.utc)


def load_train(path: Path, start: datetime, end: datetime) -> Bars:
    """Load only train OHLC; rows after end are never parsed beyond timestamp."""
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError("train bounds must be ordered timezone-aware datetimes")
    stamps, opens, highs, lows, closes = [], [], [], [], []
    previous: datetime | None = None
    with path.resolve().open(newline="") as handle:
        for number, row in enumerate(csv.reader(handle), 1):
            if len(row) < 2:
                raise ValueError(f"invalid H4 row {number}")
            stamp = _timestamp(row[0], row[1])
            if previous is not None and stamp <= previous:
                raise ValueError("H4 timestamps must be strictly increasing")
            previous = stamp
            if stamp > end:
                break
            if stamp < start:
                continue
            if len(row) != 7:
                raise ValueError(f"invalid H4 row {number}")
            try:
                values = tuple(float(value) for value in row[2:6])
            except ValueError as exc:
                raise ValueError(f"invalid train OHLC row {number}") from exc
            open_, high, low, close = values
            if (not all(math.isfinite(value) and value > 0 for value in values)
                    or high < max(open_, close) or low > min(open_, close)
                    or high < low):
                raise ValueError(f"invalid train OHLC row {number}")
            stamps.append(stamp); opens.append(open_); highs.append(high)
            lows.append(low); closes.append(close)
    if not stamps:
        raise ValueError("no H4 train bars")
    segment = np.zeros(len(stamps), dtype=np.int64)
    for index in range(1, len(stamps)):
        segment[index] = segment[index - 1] + int(
            (stamps[index] - stamps[index - 1]).total_seconds() != H4_SECONDS)
    return Bars(tuple(stamps), *(np.asarray(values, dtype=np.float64) for values in
                                 (opens, highs, lows, closes)), segment)


def true_range_and_atr(bars: Bars) -> tuple[np.ndarray, np.ndarray]:
    count = len(bars)
    tr = np.full(count, np.nan)
    atr = np.full(count, np.nan)
    for index in range(count):
        if index == 0 or bars.segment[index] != bars.segment[index - 1]:
            tr[index] = bars.high[index] - bars.low[index]
        else:
            tr[index] = max(bars.high[index] - bars.low[index],
                            abs(bars.high[index] - bars.close[index - 1]),
                            abs(bars.low[index] - bars.close[index - 1]))
        first = index - ATR_PERIOD + 1
        if first >= 0 and bars.segment[first] == bars.segment[index]:
            atr[index] = float(np.mean(tr[first:index + 1]))
    return tr, atr


def signals(bars: Bars, mechanism: str, direction: str,
            parameters: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if direction not in {"long", "short", "both"}:
        raise ValueError("invalid direction")
    period = int(parameters["indicator_period"])
    shift = int(parameters["shift"])
    if period <= 0 or shift not in (1, 2):
        raise ValueError("invalid signal parameters")
    _, atr = true_range_and_atr(bars)
    long = np.zeros(len(bars), dtype=bool)
    short = np.zeros(len(bars), dtype=bool)
    endpoint_atr = np.full(len(bars), np.nan)
    for decision in range(len(bars) - 1):
        endpoint = decision - (shift - 1)
        first = endpoint - period
        if (first < 0 or bars.segment[first] != bars.segment[endpoint]
                or not math.isfinite(atr[endpoint])):
            continue
        endpoint_atr[decision] = atr[endpoint]
        if mechanism in {"channel_breakout", "volatility_compression_breakout"}:
            up = bars.close[endpoint] > float(np.max(bars.high[first:endpoint]))
            down = bars.close[endpoint] < float(np.min(bars.low[first:endpoint]))
            if mechanism == "volatility_compression_breakout":
                lookback = int(parameters["compression_lookback"])
                compression_first = endpoint - lookback
                if (compression_first < 0
                        or bars.segment[compression_first] != bars.segment[endpoint]):
                    continue
                normalized = atr[compression_first:endpoint] / bars.close[
                    compression_first:endpoint]
                if len(normalized) != lookback or not np.all(np.isfinite(normalized)):
                    continue
                threshold = float(np.percentile(
                    normalized, float(parameters["compression_percentile"]),
                    method="linear"))
                compressed = atr[endpoint] / bars.close[endpoint] <= threshold
                up = up and compressed; down = down and compressed
        elif mechanism == "time_series_momentum":
            roc = 100 * (bars.close[endpoint] / bars.close[first] - 1)
            threshold = float(parameters["roc_threshold_pct"])
            up, down = roc > threshold, roc < -threshold
        else:
            raise ValueError("invalid mechanism")
        if up and down:  # Explicit ambiguity rule, including negative ROC thresholds.
            continue
        long[decision] = bool(up and direction in {"long", "both"})
        short[decision] = bool(down and direction in {"short", "both"})
    return long, short, endpoint_atr


def simulate(bars: Bars, mechanism: str, direction: str,
             parameters: dict[str, Any]) -> list[Trade]:
    long, short, endpoint_atr = signals(bars, mechanism, direction, parameters)
    hold = int(parameters["exit_after_bars"])
    stop_multiple = float(parameters["atr_stop_multiple"])
    if hold <= 0 or not math.isfinite(stop_multiple) or stop_multiple <= 0:
        raise ValueError("invalid exit parameters")
    trades: list[Trade] = []
    decision = 0
    while decision < len(bars) - 1:
        side = 1 if long[decision] else (-1 if short[decision] else 0)
        if not side:
            decision += 1; continue
        entry = decision + 1
        if (bars.segment[entry] != bars.segment[decision]
                or not math.isfinite(endpoint_atr[decision])):
            decision += 1; continue
        entry_price = float(bars.open[entry])
        stop = entry_price - side * endpoint_atr[decision] * stop_multiple
        completed: Trade | None = None
        for exit_index in range(entry, min(len(bars), entry + hold)):
            if bars.segment[exit_index] != bars.segment[entry]:
                break  # Exclude, do not invent an exit at a data gap.
            stopped = (bars.low[exit_index] <= stop if side == 1
                       else bars.high[exit_index] >= stop)
            timed = exit_index - entry + 1 >= hold
            if not stopped and not timed:
                continue
            exit_price = float(stop if stopped else bars.close[exit_index])
            gross_return = side * (exit_price / entry_price - 1)
            completed = Trade(side, entry, exit_index, entry_price, exit_price,
                              gross_return, exit_index - entry + 1,
                              "stop" if stopped else "time",
                              bars.timestamps[exit_index].year)
            break
        if completed is not None:
            trades.append(completed)
            decision = completed.exit_index
        else:
            decision = entry
        decision += 1
    return trades


def metrics(trades: list[Trade], costs: dict[str, Any], scenario: str,
            notional_usdc: float = 200,
            calendar_years: set[int] | None = None) -> dict[str, Any]:
    if scenario not in SCENARIOS or notional_usdc != 200:
        raise ValueError("screen requires a frozen 200 USDC scenario")
    model = (costs.get("by_notional") or {}).get("200") or {}
    carry = costs.get("carry") or {}
    bps = float(model[f"{scenario}_roundtrip_bps"])
    pnls: list[float] = []
    years = {year: 0.0 for year in sorted(
        calendar_years if calendar_years is not None
        else {trade.exit_year for trade in trades})}
    for trade in trades:
        side = "long" if trade.side == 1 else "short"
        annual_pct = float((carry.get(side) or {})[f"{scenario}_annual_cost_pct"])
        carry_return = annual_pct / 100 * (trade.holding_bars * 4) / (365.25 * 24)
        pnl = notional_usdc * (trade.gross_return - bps / 10_000 - carry_return)
        pnls.append(pnl)
        years[trade.exit_year] = years.get(trade.exit_year, 0.0) + pnl
    gross_profit = sum(max(value, 0) for value in pnls)
    gross_loss = -sum(min(value, 0) for value in pnls)
    equity = np.cumsum(pnls) if pnls else np.asarray([], dtype=float)
    peaks = np.maximum.accumulate(np.concatenate(([0.0], equity)))
    drawdown = peaks[1:] - equity if len(equity) else np.asarray([], dtype=float)
    return {
        "scenario": scenario, "closed_trades": len(trades),
        "net_pnl_usdc": sum(pnls),
        "expectancy_usdc_per_trade": sum(pnls) / len(pnls) if pnls else None,
        "profit_factor": (gross_profit / gross_loss if gross_loss > 0
                          else (None if gross_profit == 0 else "Infinity")),
        "max_drawdown_usdc": float(np.max(drawdown)) if len(drawdown) else 0.0,
        "roundtrip_bps": bps, "notional_usdc": notional_usdc,
        "calendar_year_net_pnl_usdc": {str(year): value for year, value in years.items()},
        "positive_calendar_years": sum(value > 0 for value in years.values()),
        "calendar_years": len(years),
        "positive_calendar_years_ratio": (
            sum(value > 0 for value in years.values()) / len(years) if years else 0.0),
    }


def evaluate_point(bars: Bars, mechanism: str, direction: str,
                   parameters: dict[str, Any], costs: dict[str, Any]) -> dict[str, Any]:
    trades = simulate(bars, mechanism, direction, parameters)
    years = {stamp.year for stamp in bars.timestamps}
    scenarios = {name: metrics(trades, costs, name, calendar_years=years)
                 for name in SCENARIOS}
    def pf_pass(value: Any) -> bool:
        return value == "Infinity" or (isinstance(value, (int, float)) and value >= 1.2)
    passed = (len(trades) >= 50
              and all(row["net_pnl_usdc"] > 0 and pf_pass(row["profit_factor"])
                      for row in scenarios.values())
              and scenarios["stress"]["positive_calendar_years_ratio"] >= .6)
    return {
        "decision": "PASS_POINT" if passed else "REJECT_POINT",
        "parameters": parameters, "mechanism": mechanism, "direction": direction,
        "closed_trades": len(trades), "scenarios": scenarios,
        "performance_scope": "train_only", "validation_accessed": False,
        "oos_accessed": False, "holdout_accessed": False,
        "paper_authorized": False, "live_authorized": False,
    }
