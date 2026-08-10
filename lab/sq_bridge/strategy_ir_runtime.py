"""Runtime vectorial determinista per als senyals de l'IR canònic Alquímia."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd


RUNTIME_SIGNAL_NODES = {
    "AND", "IsRising", "IsFalling", "CrossesAbove", "CrossesBelow",
    "IsGreater", "IsLower", "Close", "Low", "High", "SMA", "EMA", "RSI",
    "ROC", "BarDayOfMonth", "BarDayOfWeekIs", "IsMonthFirstTradingDay",
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
