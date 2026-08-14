#!/usr/bin/env python3
"""Hash-locked cross-sectional and 52-week-high portfolio screens."""
from __future__ import annotations

import argparse, csv, hashlib, json, math
from pathlib import Path
from statistics import mean, pstdev

HERE = Path(__file__).resolve().parent
MOM = HERE / "cross_sectional_momentum_preregistration_v1.json"
MOM_LOCK = HERE / "cross_sectional_momentum_preregistration_v1.lock.json"
HIGH = HERE / "known_52week_high_preregistration_v1.json"
HIGH_LOCK = HERE / "known_52week_high_preregistration_v1.lock.json"


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(spec: Path, lock: Path) -> dict:
    data, seal = json.loads(spec.read_text()), json.loads(lock.read_text())
    if sha(spec) != seal["preregistration_sha256"] or data["status"] != "FROZEN_BEFORE_PERFORMANCE":
        raise ValueError("frozen preregistration mismatch")
    return data


def load(path: Path) -> dict[str, tuple[float, float]]:
    if "2025" in path.name: raise ValueError("2025 filename refused")
    out = {}
    for row in csv.reader(path.open(newline="", encoding="utf-8-sig")):
        if not row or row[0].lower() == "date": continue
        day = row[0].replace(".", "-")
        if day > "2024-12-31": raise ValueError("2025 row refused")
        offset = 2 if ":" in row[1] else 1
        out[day] = (float(row[offset]), float(row[offset + 3]))
    return out


def rebalance_indices(days: list[str], cadence: str) -> list[int]:
    groups = {}
    for i, day in enumerate(days):
        key = day[:7] if cadence.startswith("monthly") else __import__("datetime").date.fromisoformat(day).isocalendar()[:2]
        groups[key] = i
    return sorted(groups.values())


def metrics(period_returns: list[tuple[str, float]]) -> dict:
    values = [x[1] for x in period_returns]
    equity = peak = 1.0; dd = 0.0
    years = {}
    for day, value in period_returns:
        equity *= 1 + value; peak = max(peak, equity); dd = max(dd, 1 - equity / peak)
        years.setdefault(day[:4], 1.0); years[day[:4]] *= 1 + value
    n = len(values); annual_factor = 52 if n and n / max(len(years), 1) > 20 else 12
    vol = pstdev(values) if len(values) > 1 else 0
    return {"observations": n, "total_return": equity - 1,
            "annualized_return": equity ** (annual_factor / n) - 1 if n and equity > 0 else None,
            "sharpe": mean(values) / vol * math.sqrt(annual_factor) if vol else None,
            "maximum_drawdown": dd,
            "positive_calendar_years": sum(v > 1 for v in years.values()),
            "calendar_years": {k: v - 1 for k, v in years.items()}}


def simulate(frames: dict, score_kind: str, lookback: int, cadence: str, top_n: int,
             start: str, end: str, absolute: bool) -> tuple[dict, float]:
    days = sorted(set.intersection(*(set(x) for x in frames.values())))
    rebalances = rebalance_indices(days, cadence)
    results, turnover, weights = [], 0.0, {}
    for signal_i in rebalances:
        entry_i = signal_i + 1
        if signal_i < lookback or entry_i >= len(days): continue
        entry_day = days[entry_i]
        if not (start <= entry_day <= end): continue
        later = next((i for i in rebalances if i > signal_i), len(days) - 1) + 1
        exit_i = min(later, len(days) - 1)
        if exit_i <= entry_i or days[exit_i] > end: continue
        scores = {}
        for asset, frame in frames.items():
            if score_kind == "return": scores[asset] = frame[days[signal_i]][1] / frame[days[signal_i-lookback]][1] - 1
            else:
                high = max(frame[days[j]][1] for j in range(signal_i-lookback+1, signal_i+1))
                scores[asset] = frame[days[signal_i]][1] / high
        ranked = sorted(scores, key=lambda a: (-scores[a], a))
        selected = [a for a in ranked if not absolute or scores[a] > 0][:top_n]
        new = {a: 1 / len(selected) for a in selected} if selected else {}
        turnover += sum(abs(new.get(a, 0) - weights.get(a, 0)) for a in frames) / 2
        weights = new
        ret = sum(w * (frames[a][days[exit_i]][0] / frames[a][entry_day][0] - 1) for a, w in weights.items())
        results.append((days[exit_i], ret))
    return metrics(results), turnover


def benchmark(frames: dict, cadence: str, start: str, end: str) -> dict:
    return simulate(frames, "return", 1, cadence, len(frames), start, end, False)[0]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--asset", action="append", required=True); ap.add_argument("--output", type=Path, required=True); args = ap.parse_args()
    mom, high = frozen(MOM, MOM_LOCK), frozen(HIGH, HIGH_LOCK)
    sources = dict(x.split("=", 1) for x in args.asset)
    if set(sources) != set(mom["universe"]): raise SystemExit("frozen five-asset universe required")
    frames = {a: load(Path(p)) for a, p in sources.items()}; periods = mom["periods"]
    report = {"schema_version": 1, "source_sha256": {a: sha(Path(p)) for a,p in sources.items()},
              "momentum_preregistration_sha256": sha(MOM), "high52_preregistration_sha256": sha(HIGH),
              "periods": {}, "holdout_2025_accessed": False, "optimized": False}
    for period, bounds in periods.items():
        block = {"benchmarks": {}, "cross_sectional": {}, "high52": {}}
        for cadence in ("weekly_last_session", "monthly_last_session"):
            block["benchmarks"][cadence] = benchmark(frames, cadence, *bounds)
            for lookback in (63,126,252):
                for top in (1,2):
                    key=f"mom_l{lookback}_{cadence[:1]}_top{top}"; m,t=simulate(frames,"return",lookback,cadence,top,*bounds,True); block["cross_sectional"][key]={"metrics":m,"turnover_one_way":t,"lookback":lookback,"cadence":cadence,"top_n":top}
        for top in (1,2):
            key=f"high252_top{top}"; m,t=simulate(frames,"high",252,"monthly_last_session",top,*bounds,False); block["high52"][key]={"metrics":m,"turnover_one_way":t,"top_n":top}
        report["periods"][period]=block
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({p:{"cross_sectional":len(v["cross_sectional"]),"high52":len(v["high52"])} for p,v in report["periods"].items()},indent=2))

if __name__ == "__main__": main()
