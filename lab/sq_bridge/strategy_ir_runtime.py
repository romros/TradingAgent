"""Runtime vectorial determinista per als senyals de l'IR canònic Alquímia."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from lab.sq_bridge.sqx_to_ir import validate_executable_ir


RUNTIME_SIGNAL_NODES = {
    "AND", "IsRising", "IsFalling", "CrossesAbove", "CrossesBelow",
    "IsGreater", "IsLower", "Close", "Low", "High", "SMA", "EMA", "RSI",
    "ROC", "Highest", "Lowest", "BarDayOfMonth", "BarDayOfWeekIs", "IsMonthFirstTradingDay",
    "IsMonthLastTradingDay", "Number", "Boolean",
}


def _param(node: dict, key: str, default=0):
    return node.get("params", {}).get(key, default)


class SignalRuntime:
    def __init__(self, frame: pd.DataFrame):
        if not isinstance(frame.index, pd.DatetimeIndex) or not frame.index.is_monotonic_increasing:
            raise ValueError("OHLC requereix DatetimeIndex creixent")
        required = {"open", "high", "low", "close"}
        if not required <= set(frame.columns) or frame[list(required)].isna().any().any():
            raise ValueError("OHLC incomplet o amb NaN")
        self.frame = frame
        self.cache: dict[str, pd.Series] = {}

    def _price(self, computed_from: int) -> pd.Series:
        if computed_from == 0:
            return self.frame["close"]
        if computed_from == 1:
            return self.frame["open"]
        if computed_from == 2:
            return self.frame["high"]
        if computed_from == 3:
            return self.frame["low"]
        if computed_from == 4:
            return (self.frame["high"] + self.frame["low"]) / 2
        if computed_from == 5:
            return (self.frame["high"] + self.frame["low"] + self.frame["close"]) / 3
        if computed_from == 6:
            return (self.frame["high"] + self.frame["low"]
                    + 2 * self.frame["close"]) / 4
        raise ValueError(f"ComputedFrom SQ invalid: {computed_from}")

    def evaluate(self, node: dict) -> pd.Series:
        key = json.dumps(node, sort_keys=True, separators=(",", ":"))
        if key in self.cache:
            return self.cache[key]
        op = node.get("op")
        if op not in RUNTIME_SIGNAL_NODES:
            raise ValueError(f"Operador IR no executable: {op}")
        children = node.get("children", [])
        shift = int(_param(node, "#Shift#", 0) or 0)
        if op in {"Close", "High", "Low"}:
            result = self.frame[op.lower()].shift(shift)
        elif op == "Number":
            result = pd.Series(float(_param(node, "#Value#", 0)), index=self.frame.index)
        elif op == "Boolean":
            result = pd.Series(bool(_param(node, "#Value#", False)), index=self.frame.index)
        elif op in {"SMA", "EMA", "RSI", "ROC"}:
            period = int(_param(node, "#Period#", 14))
            if period < 1:
                raise ValueError(f"Periode invalid per {op}: {period}")
            close = self.frame["close"]
            if op == "SMA":
                result = close.rolling(period, min_periods=period).mean()
            elif op == "EMA":
                result = close.ewm(span=period, adjust=False, min_periods=period).mean()
            elif op == "ROC":
                result = (close / close.shift(period) - 1.0) * 100
            else:
                delta = close.diff()
                avg_gain = delta.clip(lower=0).ewm(
                    alpha=1 / period, adjust=False, min_periods=period).mean()
                avg_loss = (-delta.clip(upper=0)).ewm(
                    alpha=1 / period, adjust=False, min_periods=period).mean()
                ratio = avg_gain / avg_loss.replace(0, np.nan)
                result = 100 - 100 / (1 + ratio)
                result = result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
                result = result.mask((avg_loss == 0) & (avg_gain == 0), 50.0)
            result = result.shift(shift)
        elif op in {"Highest", "Lowest"}:
            period = int(_param(node, "#Period#", 14))
            if period < 1:
                raise ValueError(f"Periode invalid per {op}: {period}")
            source = self._price(int(_param(node, "#ComputedFrom#", 0)))
            window = source.rolling(period, min_periods=period)
            result = (window.max() if op == "Highest" else window.min()).shift(shift)
        elif op == "AND":
            if not children:
                raise ValueError("AND IR sense fills")
            result = pd.Series(True, index=self.frame.index)
            for child in children:
                result &= self.evaluate(child).fillna(False).astype(bool)
        elif op in {"IsGreater", "IsLower", "CrossesAbove", "CrossesBelow"}:
            if len(children) != 2:
                raise ValueError(f"{op} requereix dos operands")
            left, right = (self.evaluate(child) for child in children)
            if op == "IsGreater":
                result = left > right
            elif op == "IsLower":
                result = left < right
            elif op == "CrossesAbove":
                result = (left > right) & (left.shift(1) <= right.shift(1))
            else:
                result = (left < right) & (left.shift(1) >= right.shift(1))
        elif op in {"IsRising", "IsFalling"}:
            if len(children) != 1:
                raise ValueError(f"{op} requereix un operand")
            value = self.evaluate(children[0]).shift(shift)
            bars = int(_param(node, "#Bars#", 1))
            if bars < 1:
                raise ValueError(f"Nombre de barres invalid per {op}")
            strict = not bool(_param(node, "#NotStrict#", False))
            result = pd.Series(True, index=self.frame.index)
            for offset in range(bars):
                current, previous = value.shift(offset), value.shift(offset + 1)
                if op == "IsRising":
                    result &= current > previous if strict else current >= previous
                else:
                    result &= current < previous if strict else current <= previous
        elif op == "BarDayOfMonth":
            result = pd.Series(self.frame.index.day, index=self.frame.index).shift(shift)
        elif op == "BarDayOfWeekIs":
            wanted = int(_param(node, "#Day#", _param(node, "#Value#", 1)))
            # Convenció SQ/MT4: diumenge=0, dilluns=1, ..., dissabte=6.
            result = pd.Series(self.frame.index.dayofweek + 1, index=self.frame.index)
            result = result.eq(wanted).shift(shift).fillna(False)
        else:
            month = pd.Series(self.frame.index.to_period("M"), index=self.frame.index)
            first = month.ne(month.shift(1))
            last = month.ne(month.shift(-1))
            if len(first):
                first.iloc[0] = False
                last.iloc[-1] = False
            result = (first if op == "IsMonthFirstTradingDay" else last)
            result = result.shift(shift).fillna(False)
        self.cache[key] = result
        return result


def evaluate_entries(ir: dict, frame: pd.DataFrame) -> dict[str, pd.Series | None]:
    if ir.get("ir_type") != "alquimia_strategy_ir":
        raise ValueError("IR Alquimia invalid")
    runtime = SignalRuntime(frame)
    return {
        direction: (None if entry is None else runtime.evaluate(entry["signal"]).fillna(False).astype(bool))
        for direction, entry in ir["entries"].items()
    }


def wilder_atr(frame: pd.DataFrame, period: int) -> pd.Series:
    if period < 1:
        raise ValueError("Periode ATR invalid")
    previous = frame["close"].shift(1)
    ranges = pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - previous).abs(),
        (frame["low"] - previous).abs(),
    ], axis=1).max(axis=1)
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    if len(frame) < period:
        return result
    result.iloc[period - 1] = ranges.iloc[:period].mean()
    for index in range(period, len(frame)):
        result.iloc[index] = ((period - 1) * result.iloc[index - 1]
                              + ranges.iloc[index]) / period
    return result


def _distance(plan: dict, entry: float, atr_value: float | None) -> float | None:
    kind = plan.get("type")
    if kind == "none":
        return None
    if kind == "percent":
        return entry * float(plan["percent"]) / 100
    if kind == "atr" and atr_value is not None and math.isfinite(atr_value):
        return float(plan["multiple"]) * atr_value
    return None


def simulate_trade_trace(ir: dict, frame: pd.DataFrame,
                         notional_usdc: float) -> dict:
    """Execute the normalized supported subset at bar opens, before costs."""
    if (not isinstance(notional_usdc, (int, float)) or isinstance(notional_usdc, bool)
            or not math.isfinite(notional_usdc) or notional_usdc <= 0):
        raise ValueError("Nocional de paritat invalid")
    if frame.index.tz is None or any(
            timestamp.utcoffset().total_seconds() != 0 for timestamp in frame.index):
        raise ValueError("La simulacio IR requereix candles UTC")
    if not frame.index.is_unique:
        raise ValueError("La simulacio IR requereix candles uniques")
    if ((frame[["open", "high", "low", "close"]] <= 0).any().any()
            or (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any()
            or (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any()):
        raise ValueError("OHLC invalid per a simulacio")
    validate_executable_ir(ir)
    entries = evaluate_entries(ir, frame)
    plans = ir.get("trade_plans")
    if not isinstance(plans, dict) or set(plans) != {"long", "short"}:
        raise ValueError("Plans de trade IR absents")
    atrs = {}
    for plan in plans.values():
        if plan is None:
            continue
        for key in ("stop_loss", "profit_target"):
            spec = plan[key]
            if spec["type"] == "atr":
                atrs[spec["period"]] = wilder_atr(frame, spec["period"])
    candles = [timestamp.isoformat().replace("+00:00", "Z")
               for timestamp in frame.index]
    signals = []
    for index, timestamp in enumerate(candles):
        for direction in ("long", "short"):
            if entries[direction] is not None and bool(entries[direction].iloc[index]):
                signals.append({"timestamp": timestamp, "direction": direction})
    trades, position = [], None

    def close(index: int, price: float, reason: str) -> None:
        nonlocal position
        sign = 1 if position["direction"] == "long" else -1
        gross_return = sign * (price - position["entry_price"]) / position["entry_price"]
        trades.append({
            "entry_timestamp": candles[position["entry_index"]],
            "exit_timestamp": candles[index], "direction": position["direction"],
            "entry_price": position["entry_price"], "exit_price": price,
            "gross_return": gross_return, "pnl": notional_usdc * gross_return,
            "exit_reason": reason,
        })
        position = None

    for index, row in enumerate(frame.itertuples()):
        occupied_at_open = position is not None
        time_exit_at_open = False
        if position is not None:
            elapsed = index - position["entry_index"]
            if position["exit_after_bars"] and elapsed >= position["exit_after_bars"]:
                close(index, float(row.open), "time")
                time_exit_at_open = True
            else:
                long = position["direction"] == "long"
                stop_hit = (position["stop"] is not None and
                            (row.low <= position["stop"] if long
                             else row.high >= position["stop"]))
                target_hit = (position["target"] is not None and
                              (row.high >= position["target"] if long
                               else row.low <= position["target"]))
                if stop_hit and target_hit:
                    raise ValueError("Stop i target intrabar amb ordre no demostrable")
                if stop_hit:
                    price = (min(float(row.open), position["stop"]) if long
                             else max(float(row.open), position["stop"]))
                    close(index, price, "stop")
                elif target_hit:
                    price = (max(float(row.open), position["target"]) if long
                             else min(float(row.open), position["target"]))
                    close(index, price, "target")
        active = [direction for direction in ("long", "short")
                  if entries[direction] is not None and bool(entries[direction].iloc[index])]
        may_enter_at_open = not occupied_at_open or time_exit_at_open
        if position is None and may_enter_at_open and active:
            if len(active) != 1:
                raise ValueError("Senyals long i short simultanis")
            direction = active[0]
            plan = plans[direction]
            if plan is None:
                raise ValueError("Senyal sense pla de trade")
            entry = float(row.open)
            stop_spec, target_spec = plan["stop_loss"], plan["profit_target"]
            stop_atr = (atrs[stop_spec["period"]].iloc[index - 1]
                        if stop_spec["type"] == "atr" and index > 0 else None)
            target_atr = (atrs[target_spec["period"]].iloc[index - 1]
                          if target_spec["type"] == "atr" and index > 0 else None)
            stop_distance = _distance(stop_spec, entry, stop_atr)
            target_distance = _distance(target_spec, entry, target_atr)
            if stop_spec["type"] != "none" and stop_distance is None:
                continue
            if target_spec["type"] != "none" and target_distance is None:
                continue
            sign = 1 if direction == "long" else -1
            position = {
                "direction": direction, "entry_index": index, "entry_price": entry,
                "stop": None if stop_distance is None else entry - sign * stop_distance,
                "target": None if target_distance is None else entry + sign * target_distance,
                "exit_after_bars": plan["exit_after_bars"],
            }
            # Orders are active during the entry bar after execution at its open.
            stop_hit = (position["stop"] is not None and
                        (row.low <= position["stop"] if sign == 1
                         else row.high >= position["stop"]))
            target_hit = (position["target"] is not None and
                          (row.high >= position["target"] if sign == 1
                           else row.low <= position["target"]))
            if stop_hit and target_hit:
                raise ValueError("Stop i target intrabar amb ordre no demostrable")
            if stop_hit:
                price = (min(entry, position["stop"]) if sign == 1
                         else max(entry, position["stop"]))
                close(index, price, "stop")
            elif target_hit:
                price = (max(entry, position["target"]) if sign == 1
                         else min(entry, position["target"]))
                close(index, price, "target")
    return {
        "schema_version": 1, "trace_type": "strategy_parity_trace",
        "source": "python", "candidate_id": ir["strategy_id"],
        "candles": candles, "signals": signals, "trades": trades,
        "notional_usdc": float(notional_usdc), "costs_applied": False,
    }
