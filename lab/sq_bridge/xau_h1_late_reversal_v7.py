#!/usr/bin/env python3
"""Single-shot independent validation for frozen XAU H1 late reversal v7."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from lab.sq_bridge.xau_h1_displacement_preflight import load_h1, prepare, simulate
from lab.sq_bridge.xau_sweep_reclaim_preflight import SCENARIOS, metrics


def _epoch(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def evaluate(root: Path, family_path: Path, stage: str = "validation") -> dict:
    family = json.loads(family_path.read_text())
    if family["legacy_quantitative_inputs"] != []:
        raise ValueError("LEGACY_QUANTITATIVE_INPUTS_FORBIDDEN")
    if family["holdout_release_authorized"] is not False:
        raise ValueError("HOLDOUT_MUST_REMAIN_SEALED")
    periods = family["periods"]
    if stage == "train":
        load_from, load_to = "2003-11-01", "2015-02-07"
        sample_from, sample_to = periods["train_from"], "2015-02-07"
    elif stage == "validation":
        load_from, load_to = "2014-11-01", "2019-07-17"
        sample_from, sample_to = periods["validation_from"], "2019-07-17"
    else:
        raise ValueError("ONLY_TRAIN_OR_VALIDATION_ALLOWED")
    # Fixed warmup precedes the requested sample; OOS and holdout are never loaded.
    frame, coverage = load_h1(root, load_from, load_to)
    trades = simulate(prepare(frame, 28), "reversal", "long", 1.5, 4, 1.5)
    start, end = _epoch(sample_from), _epoch(sample_to)
    selected = [t for t in trades if start <= t["signal_ts"] < end
                and t["signal_session_start_utc"] == 20
                and t["signal_minute_count"] >= 50
                and t["entry_minute_count"] >= 50]
    result_metrics = {scenario.name: metrics(selected, scenario) for scenario in SCENARIOS}
    stress = result_metrics["stress"]; gate = family["validation_gate"]
    checks = {
        "minimum_trades": stress["trades"] >= gate["minimum_trades"],
        "stress_profit_factor": (stress["profit_factor"] or 0) >= gate["minimum_stress_profit_factor"],
        "positive_year_ratio": stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"],
        "maximum_drawdown": stress["max_drawdown_pct"] <= gate["maximum_stress_drawdown_pct"],
    }
    return {
        "schema_version": 1, "hypothesis_id": family["hypothesis_id"],
        "stage": "train_discovery" if stage=="train" else "independent_temporal_validation",
        "parameters_frozen": True,
        "selection_bias_acknowledged": True, "sample_from": sample_from,
        "sample_to_exclusive": sample_to, "oos_accessed": False,
        "holdout_accessed": False, "coverage": coverage,
        "cost_scenarios": [asdict(s) for s in SCENARIOS], "metrics": result_metrics,
        "gate": gate, "checks": checks,
        "verdict": (("DISCOVERY_PASS" if stage=="train" else "PASS_TO_OOS")
                    if all(checks.values()) else ("DISCOVERY_FAIL" if stage=="train" else "REJECT_FAMILY_V7")),
        "family_sha256": hashlib.sha256(family_path.read_bytes()).hexdigest(),
    }


def validate(root: Path, family_path: Path) -> dict:
    return evaluate(root,family_path,"validation")


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--root",type=Path,required=True)
    p.add_argument("--family",type=Path,required=True); p.add_argument("--output",type=Path,required=True)
    p.add_argument("--stage",choices=("train","validation"),default="validation")
    a=p.parse_args(); result=evaluate(a.root,a.family,a.stage); a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))


if __name__ == "__main__": main()
