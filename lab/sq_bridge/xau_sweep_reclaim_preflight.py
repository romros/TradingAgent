#!/usr/bin/env python3
"""Train-only stability preflight for the native XAU H4 sweep/reclaim family.

This is a cheap falsification map, not the execution-parity backtest.  It uses
complete Dukascopy H4 OHLC bars and resolves an ambiguous stop/target bar
against the strategy (stop first).  A surviving region must later be retested
with M1 sequencing in SQ and Python before it can consume validation data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

TRAIN_FROM = "2004-01-01"
TRAIN_TO_EXCLUSIVE = "2015-02-07"
H4_SECONDS = 14_400
EXPECTED_MINUTES = 240


@dataclass(frozen=True)
class CostScenario:
    name: str
    roundtrip_bps: float
    annual_funding_pct: float


SCENARIOS = (
    CostScenario("base", 8.0, 4.0),
    CostScenario("conservative", 12.0, 8.0),
    CostScenario("stress", 20.0, 12.0),
)


@dataclass(frozen=True)
class Parameters:
    direction: str
    lookback: int
    exit_bars: int
    atr_period: int
    stop_atr: float
    target_atr: float


def _epoch(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def load_h4(root: Path, start: str = TRAIN_FROM,
            end_exclusive: str = TRAIN_TO_EXCLUSIVE) -> tuple[pd.DataFrame, dict]:
    """Read Dukascopy M1 into the same sparse UTC H4 buckets used by BS/SQ."""
    import duckdb

    pattern = root / "XAUUSD" / "tf=1m" / "year=*" / "month=*" / "data.parquet"
    files = sorted((root / "XAUUSD" / "tf=1m").glob("year=*/month=*/data.parquet"))
    selected = [p for p in files if start[:4] <= p.parts[-3].split("=")[1] <= end_exclusive[:4]]
    if not selected:
        raise FileNotFoundError(pattern)
    sql = """
      SELECT CAST(floor(ts / 14400) * 14400 AS BIGINT) ts,
             arg_min(open, ts) open, max(high) high, min(low) low,
             arg_max("close", ts) AS close_price, sum(volume) volume,
             count(DISTINCT ts) minute_count
      FROM read_parquet(?, hive_partitioning=false)
      WHERE ts >= ? AND ts < ?
      GROUP BY 1 ORDER BY 1
    """
    con = duckdb.connect(database=":memory:")
    raw = con.execute(sql, [str(pattern), _epoch(start), _epoch(end_exclusive)]).fetchdf()
    con.close()
    if raw.empty:
        raise RuntimeError("Dukascopy XAUUSD train dataset is empty")
    duplicates = int((raw["minute_count"] > EXPECTED_MINUTES).sum())
    observed = raw.copy()
    observed.index = pd.to_datetime(observed.ts, unit="s", utc=True)
    fingerprint = hashlib.sha256("".join(
        f"{p}:{p.stat().st_size}:{p.stat().st_mtime_ns}\n" for p in selected
    ).encode()).hexdigest()
    coverage = {
        "source": "BrokerageService Dukascopy XAUUSD M1 parquet",
        "alignment": "UTC H4 buckets at 00:00,04:00,...,20:00",
        "from": start, "to_exclusive": end_exclusive,
        "h4_bars": int(len(raw)),
        "full_240_minute_bars": int((raw.minute_count == EXPECTED_MINUTES).sum()),
        "sparse_bars_retained": int((raw.minute_count < EXPECTED_MINUTES).sum()),
        "sparse_bar_policy": "retain: no-tick M1 candles are absent in Dukascopy; matches existing BS aggregation",
        "minute_count_quantiles": {
            str(q): int(raw.minute_count.quantile(q, interpolation="nearest"))
            for q in (0.01, 0.05, 0.25, 0.5, 0.75)
        },
        "impossible_duplicate_bars": duplicates,
        "first_bar": observed.index.min().isoformat(),
        "last_bar": observed.index.max().isoformat(),
        "source_files": len(selected), "source_fingerprint": fingerprint,
    }
    observed = observed.rename(columns={"close_price": "close"})
    return observed[["ts", "open", "high", "low", "close", "volume"]], coverage


def add_indicators(frame: pd.DataFrame, lookback: int, atr_period: int) -> pd.DataFrame:
    """Prior range excludes the signal bar; ATR is known at signal close."""
    f = frame.copy()
    previous_close = f.close.shift(1)
    true_range = pd.concat([
        f.high - f.low,
        (f.high - previous_close).abs(),
        (f.low - previous_close).abs(),
    ], axis=1).max(axis=1)
    f["atr"] = true_range.ewm(alpha=1 / atr_period, adjust=False,
                               min_periods=atr_period).mean()
    f["prior_low"] = f.low.shift(1).rolling(lookback, min_periods=lookback).min()
    f["prior_high"] = f.high.shift(1).rolling(lookback, min_periods=lookback).max()
    f["long_signal"] = (f.low < f.prior_low) & (f.close > f.prior_low)
    f["short_signal"] = (f.high > f.prior_high) & (f.close < f.prior_high)
    return f


def simulate(frame: pd.DataFrame, params: Parameters, *, prepared: bool = False) -> list[dict]:
    """One position at a time; entry is next H4 open, exits are gap aware."""
    f = frame if prepared else add_indicators(frame, params.lookback, params.atr_period)
    rows = list(f.itertuples())
    trades: list[dict] = []
    next_free = 0
    for signal_i, signal in enumerate(rows[:-1]):
        if signal_i < next_free or not math.isfinite(float(signal.atr)):
            continue
        long_ok = params.direction in ("long", "both") and bool(signal.long_signal)
        short_ok = params.direction in ("short", "both") and bool(signal.short_signal)
        if long_ok == short_ok:  # neither, or contradictory simultaneous signal
            continue
        direction = 1 if long_ok else -1
        entry_i = signal_i + 1
        entry_bar = rows[entry_i]
        entry = float(entry_bar.open)
        atr = float(signal.atr)
        stop = entry - direction * params.stop_atr * atr
        target = entry + direction * params.target_atr * atr
        last_i = min(entry_i + params.exit_bars - 1, len(rows) - 1)
        exit_price = float(rows[last_i].close)
        reason = "time"
        ambiguous = False
        exit_i = last_i
        mae = 0.0
        for bar_i in range(entry_i, last_i + 1):
            bar = rows[bar_i]
            adverse = ((entry - float(bar.low)) if direction == 1
                       else (float(bar.high) - entry)) / entry
            mae = max(mae, adverse)
            if direction == 1:
                stop_hit, target_hit = float(bar.low) <= stop, float(bar.high) >= target
                gap_stop, gap_target = float(bar.open) <= stop, float(bar.open) >= target
            else:
                stop_hit, target_hit = float(bar.high) >= stop, float(bar.low) <= target
                gap_stop, gap_target = float(bar.open) >= stop, float(bar.open) <= target
            if gap_stop:
                exit_price, reason, exit_i = float(bar.open), "gap_stop", bar_i
            elif gap_target:
                exit_price, reason, exit_i = float(bar.open), "gap_target", bar_i
            elif stop_hit:  # conservative if stop and target both occur in this H4
                ambiguous = bool(target_hit)
                exit_price, reason, exit_i = stop, "stop", bar_i
            elif target_hit:
                exit_price, reason, exit_i = target, "target", bar_i
            else:
                continue
            break
        gross = direction * (exit_price / entry - 1.0)
        trades.append({
            "entry_ts": int(entry_bar.ts), "exit_ts": int(rows[exit_i].ts) + H4_SECONDS,
            "year": datetime.fromtimestamp(int(entry_bar.ts), timezone.utc).year,
            "direction": direction, "entry": entry, "exit": exit_price,
            "stop": stop, "target": target,
            "gross_return": gross, "mae": mae, "reason": reason,
            "ambiguous_h4": ambiguous,
        })
        next_free = exit_i + 1
    return trades


def metrics(trades: list[dict], scenario: CostScenario) -> dict:
    if not trades:
        return {"trades": 0, "profit_factor": 0.0, "expectancy_bps": 0.0,
                "compound_return_pct": 0.0, "max_drawdown_pct": 0.0,
                "positive_year_ratio": 0.0}
    net = []
    by_year: dict[int, list[float]] = {}
    for trade in trades:
        held_years = (trade["exit_ts"] - trade["entry_ts"]) / (365.25 * 86_400)
        value = (trade["gross_return"] - scenario.roundtrip_bps / 10_000
                 - scenario.annual_funding_pct / 100 * held_years)
        net.append(value)
        by_year.setdefault(trade["year"], []).append(value)
    values = np.asarray(net)
    wins = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    equity = np.cumprod(1 + values)
    peak = np.maximum.accumulate(np.concatenate(([1.0], equity)))[:-1]
    dd = np.maximum(0, 1 - equity / peak)
    positive_years = sum(math.prod(1 + x for x in year) > 1 for year in by_year.values())
    return {
        "trades": len(trades),
        "profit_factor": round(wins / losses, 6) if losses else None,
        "expectancy_bps": round(float(values.mean()) * 10_000, 6),
        "compound_return_pct": round(float(equity[-1] - 1) * 100, 6),
        "max_drawdown_pct": round(float(dd.max()) * 100, 6),
        "positive_year_ratio": round(positive_years / len(by_year), 6),
        "years_observed": len(by_year),
        "max_mae_pct": round(max(t["mae"] for t in trades) * 100, 6),
        "ambiguous_h4_exits": sum(bool(t.get("ambiguous_h4")) for t in trades),
    }


def parameter_grid() -> Iterable[Parameters]:
    """Frozen coarse grid: 3*5*5*2*3*3 = 1,350 deterministic points."""
    for direction in ("long", "short", "both"):
        for lookback in (5, 10, 20, 40, 60):
            for exit_bars in (2, 4, 6, 8, 12):
                for atr_period in (14, 28):
                    for stop_atr in (1.0, 2.0, 3.0):
                        for target_atr in (1.0, 2.0, 3.0):
                            yield Parameters(direction, lookback, exit_bars, atr_period,
                                             stop_atr, target_atr)


def _is_pass(row: dict) -> bool:
    stress = row["metrics"]["stress"]
    return (stress["trades"] >= 50 and (stress["profit_factor"] or 0) >= 1.05
            and stress["positive_year_ratio"] >= 0.6
            and stress["expectancy_bps"] > 0)


def stability_counts(rows: list[dict]) -> None:
    """Count passing one-step orthogonal neighbours; isolated optima fail."""
    fields = ("direction", "lookback", "exit_bars", "atr_period", "stop_atr", "target_atr")
    index = {tuple(row["parameters"][f] for f in fields): row for row in rows}
    axes = {
        "lookback": (5, 10, 20, 40, 60), "exit_bars": (2, 4, 6, 8, 12),
        "atr_period": (14, 28), "stop_atr": (1.0, 2.0, 3.0),
        "target_atr": (1.0, 2.0, 3.0),
    }
    for row in rows:
        p = row["parameters"]
        neighbours = 0
        for field, values in axes.items():
            pos = values.index(p[field])
            for neighbour_pos in (pos - 1, pos + 1):
                if 0 <= neighbour_pos < len(values):
                    candidate = dict(p); candidate[field] = values[neighbour_pos]
                    other = index.get(tuple(candidate[f] for f in fields))
                    neighbours += bool(other and _is_pass(other))
        row["passes_stress_gate"] = _is_pass(row)
        row["passing_orthogonal_neighbours"] = neighbours
        row["stable_region_member"] = _is_pass(row) and neighbours >= 2


def run(root: Path) -> dict:
    frame, coverage = load_h4(root)
    rows = []
    indicator_cache: dict[tuple[int, int], pd.DataFrame] = {}
    for params in parameter_grid():
        key = (params.lookback, params.atr_period)
        if key not in indicator_cache:
            indicator_cache[key] = add_indicators(frame, *key)
        trades = simulate(indicator_cache[key], params, prepared=True)
        rows.append({"parameters": asdict(params),
                     "metrics": {s.name: metrics(trades, s) for s in SCENARIOS}})
    stability_counts(rows)
    stable = [row for row in rows if row["stable_region_member"]]
    ranked = sorted(stable, key=lambda r: (
        r["metrics"]["stress"]["profit_factor"] or 0,
        r["passing_orthogonal_neighbours"]), reverse=True)
    return {
        "schema_version": 1,
        "experiment": "xau_h4_sweep_reclaim_v5_train_preflight",
        "decision_scope": "train-only falsification; cannot promote to paper or live",
        "holdout_accessed": False,
        "execution_model": "sparse Dukascopy H4 OHLC; stop-first ambiguity; M1 parity required",
        "coverage": coverage,
        "cost_scenarios": [asdict(s) for s in SCENARIOS],
        "grid_points": len(rows), "stress_gate_passes": sum(_is_pass(r) for r in rows),
        "stable_region_members": len(stable),
        "verdict": "CONTINUE_TO_M1_AND_SQ_OPTIMIZER" if stable else "REJECT_FAMILY_V5",
        "top_stable": ranked[:20], "rows": rows,
    }


def build_summary(result: dict, full_artifact: Path) -> dict:
    """Small, committable decision artifact backed by the full ignored grid."""
    rows = result["rows"]
    best = {}
    for scenario in ("base", "conservative", "stress"):
        best[scenario] = {}
        for direction in ("long", "short", "both"):
            eligible = [r for r in rows if r["parameters"]["direction"] == direction]
            best[scenario][direction] = max(
                eligible, key=lambda r: r["metrics"][scenario]["profit_factor"] or 0
            )
    neutral_parameters = asdict(Parameters("both", 20, 6, 14, 2.0, 2.0))
    neutral = next(r for r in rows if r["parameters"] == neutral_parameters)
    return {
        "schema_version": 1, "experiment": result["experiment"],
        "decision_scope": result["decision_scope"],
        "holdout_accessed": result["holdout_accessed"],
        "execution_model": result["execution_model"], "coverage": result["coverage"],
        "cost_scenarios": result["cost_scenarios"],
        "grid_points": result["grid_points"],
        "stress_gate_passes": result["stress_gate_passes"],
        "stable_region_members": result["stable_region_members"],
        "verdict": result["verdict"], "best_by_scenario_and_direction": best,
        "neutral_seed_control": neutral,
        "full_artifact": str(full_artifact),
        "full_artifact_sha256": hashlib.sha256(full_artifact.read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="historical_parquet root from BrokerageService")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    result = run(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            json.dumps(build_summary(result, args.output), indent=2) + "\n"
        )
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
