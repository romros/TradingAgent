#!/usr/bin/env python3
"""Post-OOS robustness audit; descriptive only, never selects new parameters."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import statistics
from pathlib import Path

from lab.sq_bridge.etf_relative_momentum_screen_v1 import load, reviews, sha
from lab.sq_bridge.etf_twelve_one_momentum_screen_v1 import LOCK, SPEC


FORMATIONS = (189, 252, 315)
SKIPS = (10, 21, 42)
COST_BPS_ONE_WAY = (0, 10, 25, 50)


def rows(frames: dict[str, dict], formation: int, skip: int,
         start: dt.date, end: dt.date) -> list[dict]:
    days = sorted(set.intersection(*(set(frame) for frame in frames.values())))
    points = reviews(days)
    result = []
    for position, signal in enumerate(points[:-1]):
        if signal < formation or signal < skip:
            continue
        next_signal = points[position + 1]
        if signal + 1 >= len(days) or next_signal + 1 >= len(days):
            continue
        entry, exit_day = days[signal + 1], days[next_signal + 1]
        if not (start <= entry and exit_day <= end):
            continue
        scores = {asset: frames[asset][days[signal - skip]][1] /
                  frames[asset][days[signal - formation]][1] - 1.0
                  for asset in frames}
        winner = min(frames, key=lambda asset: (-scores[asset], asset))
        selected = winner if scores[winner] > 0 else None
        value = (frames[winner][exit_day][0] /
                 frames[winner][entry][0] - 1.0 if selected else 0.0)
        result.append({"entry": entry.isoformat(), "exit": exit_day.isoformat(),
                       "asset": selected, "gross_return": value})
    return result


def apply_costs(observations: list[dict], bps: int) -> list[float]:
    previous = None
    values = []
    for row in observations:
        current = row["asset"]
        turnover = 0 if current == previous else int(previous is not None) + int(current is not None)
        values.append(row["gross_return"] - turnover * bps / 10_000)
        previous = current
    return values


def metrics(values: list[float]) -> dict:
    equity = peak = 1.0
    dd = 0.0
    for value in values:
        equity *= 1 + value
        peak = max(peak, equity)
        dd = max(dd, 1 - equity / peak)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return {"observations": len(values), "total_return": equity - 1,
            "annualized_sharpe": statistics.mean(values) / sd * math.sqrt(12) if sd else None,
            "maximum_drawdown": dd,
            "positive_month_fraction": sum(value > 0 for value in values) / len(values) if values else 0}


def bootstrap(values: list[float], seed: int = 1201,
              simulations: int = 10_000, block: int = 3) -> dict:
    rng = random.Random(seed)
    returns, drawdowns = [], []
    for _ in range(simulations):
        sample = []
        while len(sample) < len(values):
            origin = rng.randrange(len(values))
            sample.extend(values[(origin + offset) % len(values)] for offset in range(block))
        result = metrics(sample[:len(values)])
        returns.append(result["total_return"])
        drawdowns.append(result["maximum_drawdown"])
    returns.sort(); drawdowns.sort()
    pick = lambda data, q: data[int(q * (len(data) - 1))]
    return {"simulations": simulations, "block_months": block,
            "probability_positive": sum(value > 0 for value in returns) / simulations,
            "total_return_p05": pick(returns, .05), "total_return_p50": pick(returns, .50),
            "total_return_p95": pick(returns, .95), "drawdown_p95": pick(drawdowns, .95)}


def audit(assets: dict[str, Path], oos_report: Path, output: Path) -> dict:
    spec, lock = json.loads(SPEC.read_text()), json.loads(LOCK.read_text())
    prior = json.loads(oos_report.read_text())
    if sha(SPEC) != lock["preregistration_sha256"] or prior["decision"] != "PASS_GROSS_OOS":
        raise ValueError("GROSS_OOS_GATE_NOT_PASSED")
    source_hashes = {name: sha(path) for name, path in assets.items()}
    if source_hashes != prior["source_sha256"]:
        raise ValueError("SOURCE_CHANGED_AFTER_OOS")
    frames = {name: load(path) for name, path in assets.items()}
    start, end = dt.date(2018, 1, 1), dt.date(2024, 12, 31)
    variants = {}
    for formation in FORMATIONS:
        for skip in SKIPS:
            observations = rows(frames, formation, skip, start, end)
            variants[f"F{formation}_S{skip}"] = {
                str(bps): metrics(apply_costs(observations, bps))
                for bps in COST_BPS_ONE_WAY}
    central_rows = rows(frames, 252, 21, start, end)
    stress_values = apply_costs(central_rows, 25)
    by_year = {str(year): metrics([value for row, value in zip(central_rows, stress_values)
                                  if row["entry"].startswith(str(year))])
               for year in range(2018, 2025)}
    positive_stress = sum(value["25"]["total_return"] > 0 for value in variants.values())
    central = variants["F252_S21"]["25"]
    passed = (positive_stress >= 6 and central["total_return"] > 0
              and central["annualized_sharpe"] >= .55
              and central["maximum_drawdown"] <= .40)
    report = {"schema_version": 1,
              "audit_type": "POST_OOS_NO_PARAMETER_SELECTION",
              "decision": "PASS_ROBUSTNESS_AND_COSTS" if passed else "REJECT_FRAGILE_POST_OOS",
              "parameter_grid": {"formation_sessions": FORMATIONS, "skip_sessions": SKIPS},
              "cost_bps_one_way": COST_BPS_ONE_WAY,
              "variants": variants, "central_stress_by_year": by_year,
              "positive_neighbours_at_25bps": positive_stress,
              "central_25bps_block_bootstrap": bootstrap(stress_values),
              "holdout_2025_plus_accessed": False,
              "next_gate": "DISTRIBUTION_SEMANTICS_AND_SQ_NATIVE" if passed else None,
              "paper_authorized": False, "live_authorized": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--oos-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assets = {name: Path(path) for name, path in (item.split("=", 1) for item in args.asset)}
    print(json.dumps(audit(assets, args.oos_report, args.output), indent=2))


if __name__ == "__main__":
    main()
