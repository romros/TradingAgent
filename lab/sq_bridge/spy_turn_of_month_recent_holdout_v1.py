#!/usr/bin/env python3
"""One-shot recent holdout for the frozen SPY turn-of-month rule."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "spy_turn_of_month_recent_holdout_preregistration_v1.json"
LOCK = HERE / "spy_turn_of_month_recent_holdout_preregistration_v1.lock.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rows(path):
    rows = []
    with Path(path).open(newline="") as handle:
        for row in csv.DictReader(handle):
            date = dt.date.fromisoformat(row["date"])
            if date > dt.date(2026, 5, 29):
                continue
            rows.append((date, float(row["open"])))
    return sorted(rows)


def load_historical_rows(path):
    rows = []
    with Path(path).open(newline="") as handle:
        for row in csv.reader(handle):
            if not row or row[0].lower() == "date":
                continue
            rows.append((dt.date.fromisoformat(row[0].replace(".", "-")), float(row[2])))
    return sorted(rows)


def trades(rows, start, end):
    months = {}
    for date, opening in rows:
        months.setdefault((date.year, date.month), []).append((date, opening))
    result = []
    for year in range(start.year - 1, end.year + 1):
        for month in range(1, 13):
            current = months.get((year, month), [])
            ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
            following = months.get((ny, nm), [])
            if not current or len(following) < 4:
                continue
            entry, exit_ = current[-1], following[3]
            if start <= entry[0] and exit_[0] <= end:
                result.append({"entry": str(entry[0]), "exit": str(exit_[0]),
                               "gross_return": exit_[1] / entry[1] - 1})
    return result


def metrics(values):
    equity = peak = 1.0
    wins = losses = 0.0
    for value in values:
        equity *= 1 + value
        peak = max(peak, equity)
        wins += max(value, 0)
        losses += max(-value, 0)
    drawdown = 0.0
    equity = peak = 1.0
    for value in values:
        equity *= 1 + value
        peak = max(peak, equity)
        drawdown = max(drawdown, 1 - equity / peak)
    mean = sum(values) / len(values)
    sd = (sum((x - mean) ** 2 for x in values) / (len(values) - 1)) ** .5
    return {"trades": len(values), "compounded_return": equity - 1,
            "mean_return": mean, "profit_factor": wins / losses if losses else None,
            "maximum_drawdown": drawdown,
            "t_stat": mean / (sd / math.sqrt(len(values))) if sd else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec, lock = json.loads(SPEC.read_text()), json.loads(LOCK.read_text())
    if sha(SPEC) != lock["preregistration_sha256"]:
        raise ValueError("preregistration lock mismatch")
    parent = HERE.parents[1] / spec["parent_result"]
    if sha(parent) != spec["parent_result_sha256"]:
        raise ValueError("parent result mismatch")
    frozen = json.loads(parent.read_text())
    historical_source = HERE.parents[1] / spec["historical_source"]
    if sha(historical_source) != spec["historical_source_sha256"]:
        raise ValueError("historical source mismatch")
    recent = trades(load_rows(args.spy), dt.date(2025, 1, 1), dt.date(2026, 5, 29))
    gross = [row["gross_return"] for row in recent]
    costs = {"gross": 0.0, "tiered_1000": .0009, "stress_1000": .0030}
    recent_metrics = {key: metrics([value - cost for value in gross])
                      for key, cost in costs.items()}
    old = frozen["periods"]
    historical_rows = load_historical_rows(historical_source)
    historical = []
    for period in ("train", "validation", "oos_2024"):
        # Aggregate inference is reconstructed from the immutable parent details
        # by rerunning the same rule on the same source rows through 2024.
        bounds = {"train": (dt.date(2017, 1, 1), dt.date(2021, 12, 31)),
                  "validation": (dt.date(2022, 1, 1), dt.date(2023, 12, 31)),
                  "oos_2024": (dt.date(2024, 1, 1), dt.date(2024, 12, 31))}[period]
        period_values = [x["gross_return"] for x in trades(historical_rows, *bounds)]
        if len(period_values) != old[period]["trades"]:
            raise ValueError("historical source cannot reproduce parent trade count")
        historical += period_values
    combined = metrics(historical + gross)
    gate = spec["gates"]
    passed = (recent_metrics["gross"]["trades"] >= gate["holdout_trades_gte"]
              and recent_metrics["gross"]["compounded_return"] > 0
              and (recent_metrics["gross"]["profit_factor"] or 0) >= gate["holdout_gross_profit_factor_gte"]
              and recent_metrics["gross"]["maximum_drawdown"] <= gate["holdout_max_drawdown_lte"]
              and recent_metrics["tiered_1000"]["compounded_return"] > 0
              and (combined["t_stat"] or -999) >= gate["combined_2017_2026_one_sided_t_stat_gte"]
              and (combined["profit_factor"] or 0) >= gate["combined_2017_2026_profit_factor_gte"])
    output = {"schema_version": 1, "decision": "PASS_RECENT_HOLDOUT" if passed else "REJECT_RECENT_HOLDOUT",
              "preregistration_sha256": sha(SPEC), "parent_result_sha256": sha(parent),
              "source_sha256": sha(args.spy), "recent": recent_metrics,
              "combined_2017_2026": combined, "trades": recent,
              "optimized": False, "recent_holdout_accessed": True,
              "paper_authorized": False, "live_authorized": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
