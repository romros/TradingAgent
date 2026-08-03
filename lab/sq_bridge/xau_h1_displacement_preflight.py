#!/usr/bin/env python3
"""Train-only Dukascopy falsification map for XAU H1 displacement v6."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from lab.sq_bridge.xau_sweep_reclaim_preflight import SCENARIOS, metrics

START = "2004-01-01"
END_EXCLUSIVE = "2015-02-07"
HOUR = 3600


@dataclass(frozen=True)
class Parameters:
    mechanism: str
    side: str
    session_start_utc: int
    weekday: str | int
    expansion_atr: float
    holding_hours: int
    atr_period: int
    stop_atr: float = 1.5


def _epoch(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def load_h1(root: Path, start: str = START,
            end_exclusive: str = END_EXCLUSIVE) -> tuple[pd.DataFrame, dict]:
    import duckdb

    base = root / "XAUUSD" / "tf=1m"
    pattern = base / "year=*" / "month=*" / "data.parquet"
    files = sorted(base.glob("year=*/month=*/data.parquet"))
    if not files:
        raise FileNotFoundError(pattern)
    query = """
      SELECT CAST(floor(ts/3600)*3600 AS BIGINT) ts,
             arg_min(open,ts) open, max(high) high, min(low) low,
             arg_max("close",ts) close_price, sum(volume) volume,
             count(DISTINCT ts) minute_count
      FROM read_parquet(?, hive_partitioning=false)
      WHERE ts>=? AND ts<? GROUP BY 1 ORDER BY 1
    """
    con = duckdb.connect(database=":memory:")
    frame = con.execute(query, [str(pattern), _epoch(start), _epoch(end_exclusive)]).fetchdf()
    con.close()
    frame = frame.rename(columns={"close_price": "close"})
    frame.index = pd.to_datetime(frame.ts, unit="s", utc=True)
    first_year, last_year = start[:4], end_exclusive[:4]
    selected = [p for p in files if first_year <= p.parts[-3].split("=")[1] <= last_year]
    fingerprint = hashlib.sha256("".join(
        f"{p}:{p.stat().st_size}:{p.stat().st_mtime_ns}\n" for p in selected
    ).encode()).hexdigest()
    return frame, {
        "source": "BrokerageService Dukascopy XAUUSD M1 parquet",
        "alignment": "UTC H1 buckets", "from": start, "to_exclusive": end_exclusive,
        "h1_bars": len(frame), "full_60_minute_bars": int((frame.minute_count == 60).sum()),
        "sparse_bars_retained": int((frame.minute_count < 60).sum()),
        "sparse_bar_policy": "retain to match BrokerageService/SQ aggregation",
        "first_bar": frame.index.min().isoformat(), "last_bar": frame.index.max().isoformat(),
        "source_fingerprint": fingerprint,
    }


def prepare(frame: pd.DataFrame, atr_period: int) -> pd.DataFrame:
    f = frame.copy()
    previous_close = f.close.shift(1)
    tr = pd.concat([f.high-f.low, (f.high-previous_close).abs(),
                    (f.low-previous_close).abs()], axis=1).max(axis=1)
    # Signal bar is compared with ATR available before that bar opened.
    f["atr"] = tr.ewm(alpha=1/atr_period, adjust=False,
                       min_periods=atr_period).mean().shift(1)
    width = (f.high-f.low).replace(0, float("nan"))
    f["close_location"] = (f.close-f.low)/width
    f["bull_event"] = (f.close > f.open) & (f.close_location >= .8)
    f["bear_event"] = (f.close < f.open) & (f.close_location <= .2)
    f["session_start_utc"] = (f.index.hour // 4) * 4
    f["weekday"] = f.index.weekday
    return f


def simulate(prepared: pd.DataFrame, mechanism: str, side: str,
             expansion_atr: float, holding_hours: int, stop_atr: float) -> list[dict]:
    rows = list(prepared.itertuples())
    trades = []
    next_free = 0
    for i, signal in enumerate(rows[:-1]):
        if i < next_free or not math.isfinite(float(signal.atr)):
            continue
        if float(signal.high-signal.low) < expansion_atr*float(signal.atr):
            continue
        event_direction = 1 if signal.bull_event else (-1 if signal.bear_event else 0)
        if not event_direction:
            continue
        direction = event_direction if mechanism == "continuation" else -event_direction
        if side != "both" and direction != (1 if side == "long" else -1):
            continue
        entry_i = i+1; last_i = min(entry_i+holding_hours-1, len(rows)-1)
        entry = float(rows[entry_i].open)
        stop = entry-direction*stop_atr*float(signal.atr)
        exit_price = float(rows[last_i].close); exit_i = last_i; reason = "time"
        mae = 0.0
        for j in range(entry_i, last_i+1):
            bar = rows[j]
            mae = max(mae, ((entry-float(bar.low)) if direction == 1
                            else (float(bar.high)-entry))/entry)
            hit = float(bar.low) <= stop if direction == 1 else float(bar.high) >= stop
            gap = float(bar.open) <= stop if direction == 1 else float(bar.open) >= stop
            if gap or hit:
                exit_price = float(bar.open) if gap else stop
                exit_i = j; reason = "gap_stop" if gap else "stop"; break
        trades.append({
            "signal_ts": int(signal.ts),
            "entry_ts": int(rows[entry_i].ts), "exit_ts": int(rows[exit_i].ts)+HOUR,
            "year": datetime.fromtimestamp(int(rows[entry_i].ts), timezone.utc).year,
            "signal_session_start_utc": int(signal.session_start_utc),
            "signal_weekday": int(signal.weekday), "direction": direction,
            "entry": entry, "exit": exit_price,
            "signal_close": float(signal.close),
            "entry_gap_return": direction*(entry/float(signal.close)-1),
            "signal_minute_count": int(signal.minute_count),
            "entry_minute_count": int(rows[entry_i].minute_count),
            "gross_return": direction*(exit_price/entry-1), "mae": mae,
            "reason": reason, "ambiguous_h4": False,
        })
        next_free = exit_i+1
    return trades


def grid() -> list[Parameters]:
    return [Parameters(mechanism, side, session, weekday, expansion, hold, atr)
            for mechanism in ("continuation", "reversal")
            for side in ("long", "short", "both")
            for session in (0, 4, 8, 12, 16, 20)
            for weekday in ("all", 0, 1, 2, 3, 4)
            for expansion in (1.0, 1.5, 2.0)
            for hold in (1, 2, 4, 8)
            for atr in (14, 28)]


def _passes(row: dict) -> bool:
    base, stress = row["metrics"]["base"], row["metrics"]["stress"]
    return (stress["trades"] >= 50 and (base["profit_factor"] or 0) >= 1.2
            and (stress["profit_factor"] or 0) >= 1.05
            and stress["positive_year_ratio"] >= .6 and stress["expectancy_bps"] > 0)


def add_stability(rows: list[dict]) -> None:
    fields = tuple(Parameters.__dataclass_fields__)
    index = {tuple(r["parameters"][f] for f in fields): r for r in rows}
    axes = {"session_start_utc": (0,4,8,12,16,20), "expansion_atr": (1.0,1.5,2.0),
            "holding_hours": (1,2,4,8), "atr_period": (14,28)}
    for row in rows:
        p = row["parameters"]; neighbours = 0
        for field, values in axes.items():
            pos = values.index(p[field])
            positions = (pos-1,pos+1)
            if field == "session_start_utc":
                positions = ((pos-1)%len(values),(pos+1)%len(values))
            for q in positions:
                if 0 <= q < len(values):
                    candidate = dict(p); candidate[field] = values[q]
                    other = index.get(tuple(candidate[f] for f in fields))
                    neighbours += bool(other and _passes(other))
        row["passes_stress_gate"] = _passes(row)
        row["passing_orthogonal_neighbours"] = neighbours
        row["stable_region_member"] = _passes(row) and neighbours >= 2


def run(root: Path) -> dict:
    frame, coverage = load_h1(root)
    prepared = {atr: prepare(frame, atr) for atr in (14,28)}
    cache = {}
    rows = []
    for p in grid():
        key = (p.mechanism,p.side,p.expansion_atr,p.holding_hours,p.atr_period,p.stop_atr)
        if key not in cache:
            cache[key] = simulate(prepared[p.atr_period], p.mechanism, p.side,
                                  p.expansion_atr, p.holding_hours, p.stop_atr)
        sample = [t for t in cache[key]
                  if t["signal_session_start_utc"] == p.session_start_utc
                  and (p.weekday == "all" or t["signal_weekday"] == p.weekday)]
        rows.append({"parameters":asdict(p),
                     "metrics":{s.name:metrics(sample,s) for s in SCENARIOS}})
    add_stability(rows)
    stable = [r for r in rows if r["stable_region_member"]]
    top = sorted(stable,key=lambda r:(r["metrics"]["stress"]["profit_factor"] or 0,
                                      r["passing_orthogonal_neighbours"]),reverse=True)[:20]
    return {"schema_version":1,"experiment":"xau_h1_displacement_session_v6_train",
            "decision_scope":"train-only falsification; cannot promote to paper or live",
            "holdout_accessed":False,"coverage":coverage,
            "cost_scenarios":[asdict(s) for s in SCENARIOS],"grid_points":len(rows),
            "stress_gate_passes":sum(_passes(r) for r in rows),
            "stable_region_members":len(stable),
            "verdict":"CONTINUE_TO_VALIDATION" if stable else "REJECT_FAMILY_V6",
            "top_stable":top,"rows":rows}


def build_summary(result: dict, full_artifact: Path) -> dict:
    rows=result["rows"]; best={}
    for scenario in ("base","conservative","stress"):
        best[scenario]={}
        for mechanism in ("continuation","reversal"):
            for side in ("long","short","both"):
                candidates=[r for r in rows if r["parameters"]["mechanism"]==mechanism
                            and r["parameters"]["side"]==side
                            and r["metrics"][scenario]["trades"]>=50]
                best[scenario][f"{mechanism}_{side}"]=max(
                    candidates,key=lambda r:r["metrics"][scenario]["profit_factor"] or 0)
    return {k:v for k,v in result.items() if k!="rows"} | {
        "best_by_scenario_mechanism_side":best,
        "full_artifact":str(full_artifact),
        "full_artifact_sha256":hashlib.sha256(full_artifact.read_bytes()).hexdigest()}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True); p.add_argument("--summary-output",type=Path); a=p.parse_args()
    result=run(a.root); a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    if a.summary_output:
        a.summary_output.parent.mkdir(parents=True,exist_ok=True)
        a.summary_output.write_text(json.dumps(build_summary(result,a.output),indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="rows"},indent=2))


if __name__ == "__main__": main()
