#!/usr/bin/env python3
"""Certifica una font D1 de MSFT contra candles M1 natives d'Ostium."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, time, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo


NY = ZoneInfo("America/New_York")


def load_ostium_m1(root: Path) -> list[dict]:
    rows = []
    for path in sorted(root.rglob("*.csv")):
        if path.name.startswith("."):
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            for raw in csv.reader(handle):
                if len(raw) < 5:
                    continue
                try:
                    ts = int(float(raw[0]))
                    dt_utc = datetime.fromtimestamp(ts, timezone.utc)
                    dt_ny = dt_utc.astimezone(NY)
                    values = [float(value) for value in raw[1:5]]
                except (TypeError, ValueError, OverflowError):
                    continue
                rows.append({"ts": ts, "dt_utc": dt_utc, "dt_ny": dt_ny,
                             "open": values[0], "high": values[1],
                             "low": values[2], "close": values[3]})
    return rows


def load_ostium_parquet_m1(root: Path, symbol: str) -> list[dict]:
    """Load quarantined Ostium rollover partitions through DuckDB.

    ``root`` is the canonical ``historical_parquet_ostium_v1`` directory.  The
    explicit symbol argument prevents a parity run from silently mixing assets.
    """
    import duckdb

    base = root / symbol.upper() / "tf=1m"
    paths = sorted(base.rglob("data.parquet"))
    if not paths:
        return []
    rows = duckdb.connect(":memory:").execute(
        'SELECT "ts", "open", "high", "low", "close" FROM read_parquet(?) ORDER BY "ts"',
        [[str(path) for path in paths]],
    ).fetchall()
    result = []
    for ts, open_, high, low, close in rows:
        dt_utc = datetime.fromtimestamp(int(ts), timezone.utc)
        result.append({"ts": int(ts), "dt_utc": dt_utc, "dt_ny": dt_utc.astimezone(NY),
                       "open": float(open_), "high": float(high),
                       "low": float(low), "close": float(close)})
    return result


def aggregate_regular_session(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped = defaultdict(list)
    anomalies = []
    for row in sorted(rows, key=lambda item: item["ts"]):
        local = row["dt_ny"]
        if local.weekday() >= 5 or not (time(9, 30) <= local.time() < time(16, 0)):
            continue
        grouped[local.date().isoformat()].append(row)
    daily = []
    for day, bars in sorted(grouped.items()):
        clean = []
        for index, bar in enumerate(bars):
            neighbours = bars[max(0, index - 3):index] + bars[index + 1:index + 4]
            centre = median([item["close"] for item in neighbours]) if neighbours else bar["close"]
            deviation = abs(bar["close"] / centre - 1) if centre > 0 else 0
            if len(neighbours) >= 2 and deviation >= 0.05:
                anomalies.append({"timestamp_utc": bar["dt_utc"].isoformat(),
                                  "neighbour_median": centre, "close": bar["close"],
                                  "absolute_deviation": deviation,
                                  "action": "EXCLUDED_ISOLATED_ORACLE_OUTLIER"})
                continue
            clean.append(bar)
        if not clean:
            continue
        robust_close = median([bar["close"] for bar in clean[-5:]])
        daily.append({"date": day, "open": clean[0]["open"],
                      "high": max(bar["high"] for bar in clean),
                      "low": min(bar["low"] for bar in clean),
                      "close": robust_close, "last_raw_close": clean[-1]["close"],
                      "close_policy": "median_last_5_regular_session_bars",
                      "bars": len(clean),
                      "raw_bars": len(bars)})
    return daily, anomalies


def fetch_yahoo(auto_adjust: bool) -> list[dict]:
    import pandas as pd
    import yfinance as yf

    frame = yf.download("MSFT", start="2026-03-01", end="2026-08-02",
                        interval="1d", auto_adjust=auto_adjust, progress=False)
    if frame is None or frame.empty:
        return []
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.droplevel(1)
    frame = frame.rename(columns=str.lower)
    return [{"date": index.date().isoformat(),
             "open": float(row["open"]), "high": float(row["high"]),
             "low": float(row["low"]), "close": float(row["close"])}
            for index, row in frame.iterrows()]


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def compare(ostium: list[dict], reference: list[dict]) -> dict:
    left = {row["date"]: row for row in ostium}
    right = {row["date"]: row for row in reference}
    dates = sorted(set(left) & set(right))
    close_bps = [abs(left[day]["close"] / right[day]["close"] - 1) * 10000
                 for day in dates if right[day]["close"] > 0]
    paired_returns = []
    for prev, current in zip(dates, dates[1:]):
        if left[prev]["close"] > 0 and right[prev]["close"] > 0:
            paired_returns.append((left[current]["close"] / left[prev]["close"] - 1,
                                   right[current]["close"] / right[prev]["close"] - 1))
    correlation = None
    if len(paired_returns) >= 2:
        xs, ys = zip(*paired_returns)
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        if vx > 0 and vy > 0:
            correlation = sum((x - mx) * (y - my) for x, y in paired_returns) / math.sqrt(vx * vy)
    return {"overlap_days": len(dates),
            "first_overlap": dates[0] if dates else None,
            "last_overlap": dates[-1] if dates else None,
            "close_diff_bps_median": median(close_bps) if close_bps else None,
            "close_diff_bps_p95": _percentile(close_bps, .95),
            "daily_return_correlation": correlation,
            "dates_only_ostium": sorted(set(left) - set(right)),
            "dates_only_reference": sorted(set(right) - set(left))}


def certify(root: Path) -> dict:
    raw = load_ostium_m1(root)
    daily, anomalies = aggregate_regular_session(raw)
    adjusted = compare(daily, fetch_yahoo(True))
    unadjusted = compare(daily, fetch_yahoo(False))
    chosen_name, chosen = min((("adjusted", adjusted), ("unadjusted", unadjusted)),
                              key=lambda item: item[1]["close_diff_bps_median"]
                              if item[1]["close_diff_bps_median"] is not None else float("inf"))
    reasons = []
    warnings = []
    if chosen["overlap_days"] < 60:
        reasons.append("OVERLAP_LT_60")
    if chosen["daily_return_correlation"] is None or chosen["daily_return_correlation"] < .98:
        reasons.append("RETURN_CORRELATION_LT_0_98")
    if chosen["close_diff_bps_median"] is None or chosen["close_diff_bps_median"] > 25:
        reasons.append("MEDIAN_CLOSE_DIFF_GT_25_BPS")
    if anomalies:
        warnings.append("OSTIUM_ISOLATED_OUTLIERS_FILTERED")
    incomplete = [row for row in daily if row["bars"] < 300]
    if incomplete:
        warnings.append("INCOMPLETE_REGULAR_SESSIONS_EXCLUDE_FROM_RESEARCH_PARITY")
    return {"schema_version": 1, "source": str(root), "raw_m1_rows": len(raw),
            "regular_session_days": len(daily), "selected_reference": chosen_name,
            "adjusted": adjusted, "unadjusted": unadjusted,
            "intraday_anomalies": anomalies, "incomplete_sessions": incomplete,
            "scope": "CLOSE_D1_ONLY_NO_RAW_OPEN_HIGH_LOW_DEPENDENCE",
            "decision": "PASS_CLOSE_ONLY" if not reasons else "BLOCK",
            "reasons": reasons, "warnings": warnings}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ostium-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = certify(args.ostium_root)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
