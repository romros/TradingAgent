"""Frozen CAT 0.168 signal and bracket mechanics for shadow observation."""
from __future__ import annotations


def wilder_sum(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    out[period] = sum(values[1:period + 1])
    for i in range(period + 1, len(values)):
        previous = out[i - 1]
        assert previous is not None
        out[i] = previous - previous / period + values[i]
    return out


def indicators(rows: list[dict]) -> tuple[list[float | None], list[float | None]]:
    if not rows:
        return [], []
    highs, lows, closes = ([float(row[key]) for row in rows]
                           for key in ("high", "low", "close"))
    tr, minus_dm = [highs[0] - lows[0]], [0.0]
    for i in range(1, len(rows)):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                      abs(lows[i] - closes[i - 1])))
        up, down = highs[i] - highs[i - 1], lows[i - 1] - lows[i]
        minus_dm.append(down if down > up and down > 0 else 0.0)
    tr40, dm40 = wilder_sum(tr, 40), wilder_sum(minus_dm, 40)
    minus_di = [None if tr40[i] in {None, 0} else 100 * dm40[i] / tr40[i]
                for i in range(len(rows))]
    atr = [None if value is None else value / 30 for value in wilder_sum(tr, 30)]
    return minus_di, atr


def entry_for_index(rows: list[dict], index: int) -> dict | None:
    """Return frozen entry terms; current bar is never used by its signal/ATR."""
    if index < 44:
        return None
    minus_di, atr = indicators(rows[:index + 1])
    values = [minus_di[index - shift] for shift in (2, 3, 4)]
    if not all(value is not None for value in values):
        return None
    if not (values[0] < values[1] and values[1] >= values[2]):
        return None
    current_atr = atr[index - 1]
    if current_atr is None:
        return None
    opening = float(rows[index]["open"])
    return {"entry": opening, "stop": opening - 2.5 * current_atr,
            "target": opening + 2.1 * current_atr, "atr30": current_atr,
            "signal_values_minus_di": values}


def bracket_exit(row: dict, stop: float, target: float) -> tuple[str, float] | None:
    opening, high, low = (float(row[key]) for key in ("open", "high", "low"))
    if opening <= stop:
        return "SL_GAP", opening
    if opening >= target:
        return "PT_GAP", opening
    if low <= stop:  # frozen pessimistic same-bar ordering
        return "SL", stop
    if high >= target:
        return "PT", target
    return None
