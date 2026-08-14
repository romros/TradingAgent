#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "turn_of_month_preregistration_v1.json"
LOCK = HERE / "turn_of_month_preregistration_v1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[dt.date, tuple[float, float]]:
    if "2025" in path.name:
        raise ValueError("2025 is sealed")
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        p = line.split(",")
        day = dt.datetime.strptime(p[0], "%Y.%m.%d").date()
        if day.year >= 2025:
            raise ValueError("row in sealed period")
        out[day] = (float(p[2]), float(p[5]))
    return out


def trades(frame: dict[dt.date, tuple[float, float]], start: dt.date, end: dt.date):
    days = sorted(frame)
    months: dict[tuple[int, int], list[dt.date]] = {}
    for day in days:
        months.setdefault((day.year, day.month), []).append(day)
    keys = sorted(months)
    result = []
    for i in range(len(keys) - 1):
        current, following = keys[i], keys[i + 1]
        if (following[0] * 12 + following[1]) != (current[0] * 12 + current[1] + 1):
            continue
        if len(months[following]) < 4:
            continue
        entry, exit_ = months[current][-1], months[following][3]
        if start <= entry and exit_ <= end:
            result.append((exit_, frame[exit_][0] / frame[entry][0] - 1.0))
    return result


def combine_equal(frames: dict[str, dict[dt.date, tuple[float, float]]], start, end):
    legs = {asset: dict(trades(frame, start, end)) for asset, frame in frames.items()}
    common = sorted(set.intersection(*(set(x) for x in legs.values())))
    return [(day, sum(legs[a][day] for a in legs) / len(legs)) for day in common]


def metrics(rows):
    rs = [x[1] for x in rows]
    if not rs:
        return {"trades": 0}
    wins, losses = sum(x > 0 for x in rs), [-x for x in rs if x < 0]
    gp = sum(x for x in rs if x > 0)
    equity = peak = 1.0
    maxdd = 0.0
    for r in rs:
        equity *= 1 + r
        peak = max(peak, equity)
        maxdd = max(maxdd, 1 - equity / peak)
    mean = sum(rs) / len(rs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in rs) / (len(rs) - 1)) if len(rs) > 1 else 0
    return {
        "trades": len(rs), "wins": wins, "mean_return": mean,
        "total_return": equity - 1, "profit_factor": gp / sum(losses) if losses else None,
        "monthly_sharpe": mean / sd * math.sqrt(12) if sd else None,
        "max_drawdown": maxdd,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spx", type=Path, required=True)
    ap.add_argument("--stock", action="append", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    spec, lock = json.loads(SPEC.read_text()), json.loads(LOCK.read_text())
    if sha(SPEC) != lock["preregistration_sha256"]:
        raise ValueError("preregistration lock mismatch")
    stock_paths = dict(x.split("=", 1) for x in args.stock)
    if set(stock_paths) != set(spec["assets"]["STOCKS"]):
        raise ValueError("frozen stock universe required")
    spx, stocks = load(args.spx), {a: load(Path(p)) for a, p in stock_paths.items()}
    report = {"schema_version": 1, "preregistration_sha256": sha(SPEC),
              "holdout_2025_accessed": False, "optimized": False, "periods": {}}
    all_rows = {"SPX": {}, "STOCKS": {}}
    for period, bounds in spec["periods"].items():
        if period == "holdout_2025":
            continue
        start, end = map(dt.date.fromisoformat, bounds)
        all_rows["SPX"][period] = trades(spx, start, end)
        all_rows["STOCKS"][period] = combine_equal(stocks, start, end)
        report["periods"][period] = {k: metrics(v[period]) for k, v in all_rows.items()}
    gates = spec["gates"]
    decisions = {}
    for label in ("SPX", "STOCKS"):
        va, oo = all_rows[label]["validation"], all_rows[label]["oos_2024"]
        combined = metrics(va + oo)
        vm, om = metrics(va), metrics(oo)
        passed = (vm["trades"] >= gates["validation_min_trades"] and
                  om["trades"] >= gates["oos_min_trades"] and
                  vm["mean_return"] > 0 and om["mean_return"] > 0 and
                  (vm["profit_factor"] or 0) >= gates["each_validation_and_oos_profit_factor_gte"] and
                  (om["profit_factor"] or 0) >= gates["each_validation_and_oos_profit_factor_gte"] and
                  (combined["monthly_sharpe"] or -999) >= gates["combined_validation_oos_monthly_sharpe_gte"] and
                  combined["max_drawdown"] <= gates["combined_validation_oos_max_drawdown_lte"])
        decisions[label] = {"pass": passed, "combined_validation_oos": combined}
    report["decisions"] = decisions
    report["transfer_gate_pass"] = all(x["pass"] for x in decisions.values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
