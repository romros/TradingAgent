"""Runtime vectorial determinista per als senyals de l'IR canònic Alquímia."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from lab.sq_bridge.sqx_to_ir import validate_executable_ir


RUNTIME_SIGNAL_NODES = {
    "AND", "Not", "IsRising", "IsFalling", "CrossesAbove", "CrossesBelow",
    "IsGreater", "IsLower", "Close", "Low", "High", "SMA", "EMA", "RSI",
    "ROC", "Highest", "Lowest", "BarDayOfMonth", "BarDayOfWeekIs", "IsMonthFirstTradingDay",
    "IsMonthLastTradingDay", "Number", "Boolean",
}


def _param(node: dict, key: str, default=0):
    return node.get("params", {}).get(key, default)


def sq_sma(values: pd.Series, period: int) -> pd.Series:
    """Exact warm-up semantics of SQ AverageCalculator.SMA."""
    return values.rolling(period, min_periods=1).mean()


def sq_ema(values: pd.Series, period: int) -> pd.Series:
    """SQ seeds EMA with bar zero, then applies alpha=2/(period+1)."""
    return values.ewm(span=period, adjust=False, min_periods=1).mean()


def sq_roc(values: pd.Series, period: int) -> pd.Series:
    previous = values.shift(period)
    result = (values - previous) / previous * 100
    return result.mask(previous.isna() | previous.eq(0), 0.0)


def sq_rsi(values: pd.Series, period: int) -> pd.Series:
    """Literal vector equivalent of the installed SQ RSICalculator.java."""
    result = pd.Series(0.0, index=values.index, dtype=float)
    if len(values) <= period:
        return result
    delta = values.diff()
    ups = delta.clip(lower=0).fillna(0.0)
    downs = (-delta.clip(upper=0)).fillna(0.0)
    avg_up = float(ups.iloc[1:period + 1].mean())
    avg_down = float(downs.iloc[1:period + 1].mean())

    def value() -> float:
        if avg_down != 0:
            return 100 - 100 / (1 + avg_up / avg_down)
        if avg_up != 0:
            return 100.0
        return 50.0

    result.iloc[period] = value()
    for index in range(period + 1, len(values)):
        avg_up = (avg_up * (period - 1) + float(ups.iloc[index])) / period
        avg_down = (avg_down * (period - 1) + float(downs.iloc[index])) / period
        result.iloc[index] = value()
    return result


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
                result = sq_sma(close, period)
            elif op == "EMA":
                result = sq_ema(close, period)
            elif op == "ROC":
                result = sq_roc(close, period)
            else:
                result = sq_rsi(close, period)
            result = result.shift(shift)
        elif op in {"Highest", "Lowest"}:
            period = int(_param(node, "#Period#", 14))
            if period < 1:
                raise ValueError(f"Periode invalid per {op}: {period}")
            source = self._price(int(_param(node, "#ComputedFrom#", 0)))
            # SQ Highest/Lowest calculators use the available prefix while warming up.
            window = source.rolling(period, min_periods=1)
            result = (window.max() if op == "Highest" else window.min()).shift(shift)
        elif op == "AND":
            if not children:
                raise ValueError("AND IR sense fills")
            result = pd.Series(True, index=self.frame.index)
            for child in children:
                result &= self.evaluate(child).fillna(False).astype(bool)
        elif op == "Not":
            if len(children) != 1:
                raise ValueError("Not IR requereix un fill")
            result = ~self.evaluate(children[0]).fillna(False).astype(bool)
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
            # Literal equivalent of the installed SQ IsRising/IsFalling Java
            # snippets.  Bars is the number of sampled values, hence Bars-1
            # comparisons.  The comparison's Shift is added to any shift
            # already present in the child block.  SQ rounds each sampled
            # value to six decimals and requires at least one strict move even
            # when equal adjacent values are allowed.
            value = self.evaluate(children[0]).round(6)
            bars = int(_param(node, "#Bars#", 1))
            if bars < 2:
                raise ValueError(f"Nombre de barres invalid per {op}")
            strict = not bool(_param(node, "#NotStrict#", False))
            previous = value.shift(bars + shift - 1)
            valid = pd.Series(True, index=self.frame.index)
            at_least_once = pd.Series(False, index=self.frame.index)
            complete = previous.notna()
            for index in range(1, bars):
                current = value.shift(bars + shift - 1 - index)
                complete &= current.notna()
                if op == "IsRising":
                    valid &= current > previous if strict else current >= previous
                    at_least_once |= current > previous
                else:
                    valid &= current < previous if strict else current <= previous
                    at_least_once |= current < previous
                previous = current
            result = complete & valid & at_least_once
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


def sq_atr(frame: pd.DataFrame, period: int) -> pd.Series:
    """Exact prefix warm-up and Wilder recurrence of SQ ATR.java."""
    if period < 1:
        raise ValueError("Periode ATR invalid")
    previous = frame["close"].shift(1)
    ranges = pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - previous).abs(),
        (frame["low"] - previous).abs(),
    ], axis=1).max(axis=1)
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    if frame.empty:
        return result
    result.iloc[0] = ranges.iloc[0]
    for index in range(1, len(frame)):
        divisor = min(index + 1, period)
        result.iloc[index] = ((divisor - 1) * result.iloc[index - 1]
                              + ranges.iloc[index]) / divisor
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
                         notional_usdc: float,
                         evaluation_start: pd.Timestamp | None = None,
                         evaluation_end: pd.Timestamp | None = None) -> dict:
    """Execute the normalized supported subset at bar opens, before costs."""
    if (not isinstance(notional_usdc, (int, float)) or isinstance(notional_usdc, bool)
            or not math.isfinite(notional_usdc) or notional_usdc <= 0):
        raise ValueError("Nocional de paritat invalid")
    if frame.index.tz is None or any(
            timestamp.utcoffset().total_seconds() != 0 for timestamp in frame.index):
        raise ValueError("La simulacio IR requereix candles UTC")
    if not frame.index.is_unique:
        raise ValueError("La simulacio IR requereix candles uniques")
    if evaluation_start is None:
        evaluation_start = frame.index[0]
    if evaluation_end is None:
        evaluation_end = frame.index[-1]
    if (evaluation_start.tzinfo is None or evaluation_end.tzinfo is None
            or evaluation_start > evaluation_end
            or evaluation_start not in frame.index or evaluation_end not in frame.index):
        raise ValueError("Finestra d'avaluacio invalida o fora de les candles")
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
                atrs[spec["period"]] = sq_atr(frame, spec["period"])
    candles = [timestamp.isoformat().replace("+00:00", "Z")
               for timestamp in frame.index]
    evaluation_mask = ((frame.index >= evaluation_start)
                       & (frame.index <= evaluation_end))
    weekend_filter = ir["execution"].get("dont_trade_on_weekends") is True
    friday_close = int(ir["execution"].get("weekend_friday_close_hhmm", 1700))
    sunday_open = int(ir["execution"].get("weekend_sunday_open_hhmm", 1700))

    def entry_time_allowed(timestamp: pd.Timestamp) -> bool:
        if not weekend_filter:
            return True
        hhmm = timestamp.hour * 100 + timestamp.minute
        if timestamp.dayofweek == 4:
            return hhmm < friday_close
        if timestamp.dayofweek == 5:
            return False
        if timestamp.dayofweek == 6:
            return hhmm >= sunday_open
        return True
    signals = []
    for index, timestamp in enumerate(candles):
        if not evaluation_mask[index]:
            continue
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
        if not evaluation_mask[index]:
            continue
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
        if (position is None and may_enter_at_open and active
                and entry_time_allowed(frame.index[index])):
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
            # SQ ATRBasedValue rounds ATR itself to six decimals before scaling.
            if stop_atr is not None:
                stop_atr = round(float(stop_atr), 6)
            if target_atr is not None:
                target_atr = round(float(target_atr), 6)
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
    if position is not None:
        final_index = int(np.flatnonzero(evaluation_mask)[-1])
        close(final_index, float(frame.iloc[final_index]["close"]), "EndTest")
    return {
        "schema_version": 1, "trace_type": "strategy_parity_trace",
        "source": "python", "candidate_id": ir["strategy_id"],
        "candles": candles, "signals": signals, "trades": trades,
        "notional_usdc": float(notional_usdc), "costs_applied": False,
        "evaluation_start": evaluation_start.isoformat().replace("+00:00", "Z"),
        "evaluation_end": evaluation_end.isoformat().replace("+00:00", "Z"),
    }
