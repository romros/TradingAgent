#!/usr/bin/env python3
"""Compile the sealed Alquimia v5 campaign into performance-blind SQ build jobs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREREG = ROOT / "lab/sq_bridge/noncrypto_campaign_preregistration_v5.json"
DEFAULT_OUTPUT = ROOT / "lab/sq_bridge/evidence/noncrypto_sq_build_plan_v5.json"
EXIT_CONTRACT = ROOT / "lab/sq_bridge/noncrypto_exit_contract_v5.json"
EXPECTED_PREREG_SHA256 = "bb637db2c65d947218d8ba49a6b0ac0ae27fcf50950b01df52821708f0a54a20"
SQ_POPULATION_PER_GENERATION = 4 * 80

RESOURCES = {
    "XAUUSD_M15": {
        "sq_symbol": "XAUUSD_M1_dukasXAUUSD_M1_dukas_NYclose",
        "source_timeframe": "M1",
        "chart_timeframe": "M15",
        "history_path": "/mnt/volume-SQ/user/data/History/XAUUSD_M1_dukasXAUUSD_M1_dukas_NYclose/XAUUSD_M1_dukasXAUUSD_M1_dukas_NYclose_M1.dat",
        "timezone": "America/New_York",
    },
    "USDJPY_M15": {
        "sq_symbol": "USDJPY_M1_dukas",
        "source_timeframe": "M1",
        "chart_timeframe": "M15",
        "history_path": "/mnt/volume-SQ/user/data/History/USDJPY_M1_dukas/USDJPY_M1_dukas_M1.dat",
        "timezone": "Etc/UTC",
    },
    "EURUSD_D1": {
        "sq_symbol": "EURUSD_ALQ_NY17_D1_V3",
        "source_timeframe": "D1",
        "chart_timeframe": "D1",
        "history_path": "/mnt/volume-SQ/user/data/History/EURUSD_ALQ_NY17_D1_V3/EURUSD_ALQ_NY17_D1_V3_D1.dat",
        "timezone": "America/New_York",
    },
    "US500_D1": {
        "sq_symbol": "US500_ALQ_RTH_D1",
        "source_timeframe": "D1",
        "chart_timeframe": "D1",
        "history_path": "/mnt/volume-SQ/user/data/History/US500_ALQ_RTH_D1/US500_ALQ_RTH_D1_D1.dat",
        "timezone": "America/New_York",
    },
}

HYPOTHESIS_MARKETS = {
    "xau-m15-macro-compression-breakout-v5": "XAUUSD_M15",
    "xau-m15-failed-shock-reversion-v5": "XAUUSD_M15",
    "usdjpy-m15-session-range-breakout-v5": "USDJPY_M15",
    "usdjpy-m15-failed-session-break-reversion-v5": "USDJPY_M15",
    "us500-d1-volatility-shock-rebound-v5": "US500_D1",
    "eurusd-d1-short-horizon-trend-v5": "EURUSD_D1",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _generation_split(total_evaluations: int, exits: int) -> list[int]:
    if total_evaluations % SQ_POPULATION_PER_GENERATION:
        raise ValueError("evaluation budget must be an exact number of generations")
    generations = total_evaluations // SQ_POPULATION_PER_GENERATION
    quotient, remainder = divmod(generations, exits)
    return [quotient + (index < remainder) for index in range(exits)]


def compile_plan(prereg_path: Path = DEFAULT_PREREG) -> dict[str, Any]:
    prereg_path = prereg_path.resolve()
    if _sha(prereg_path) != EXPECTED_PREREG_SHA256:
        raise ValueError("sealed preregistration hash changed")
    campaign = _load(prereg_path)
    exit_contract = _load(EXIT_CONTRACT)
    if any((campaign.get("performance_accessed"), campaign.get("holdout_accessed"),
            campaign.get("sqcli_executed"), campaign.get("crypto_allowed"))):
        raise ValueError("campaign is no longer eligible for blind SQ compilation")
    sq = campaign["sq_generation"]
    if (sq["algorithm"], sq["islands"], sq["population_per_island"]) != (
            "EVOLUTIONARY_ISLANDS", 4, 80):
        raise ValueError("sealed evolutionary shape changed")

    jobs: list[dict[str, Any]] = []
    for hypothesis in campaign["hypothesis_search_spaces"]:
        hypothesis_id = hypothesis["hypothesis_id"]
        try:
            market_key = HYPOTHESIS_MARKETS[hypothesis_id]
        except KeyError as exc:
            raise ValueError(f"unmapped sealed hypothesis: {hypothesis_id}") from exc
        exits = hypothesis["axes"]["exit_template"]
        generation_split = _generation_split(hypothesis["evaluation_budget"], len(exits))
        numeric_axes = {key: values for key, values in hypothesis["axes"].items()
                        if key != "exit_template"}
        for index, (exit_template, generations) in enumerate(zip(exits, generation_split), 1):
            evaluations = generations * SQ_POPULATION_PER_GENERATION
            resolved_exit = exit_contract["preregistration_aliases"].get(exit_template,
                                                                          exit_template)
            try:
                exit_semantics = exit_contract["templates"][resolved_exit]
            except KeyError as exc:
                raise ValueError(f"unresolved exit template: {exit_template}") from exc
            jobs.append({
                "job_id": f"{hypothesis_id}__exit-{index}",
                "hypothesis_id": hypothesis_id,
                "market_key": market_key,
                "resource": RESOURCES[market_key],
                "train_period": campaign["temporal_splits"][market_key]["train"],
                "future_periods_embargoed": ["validation", "oos", "holdout"],
                "direction": "LONG" if hypothesis_id.startswith("us500-") else "BOTH",
                "entry_block": f"AlquimiaV5{''.join(part.title() for part in hypothesis_id.removesuffix('-v5').split('-'))}",
                "allowed_entry_components": hypothesis["allowed_entry_blocks"],
                "numeric_axes": numeric_axes,
                "fixed_exit_template": exit_template,
                "resolved_exit_template": resolved_exit,
                "exit_semantics": exit_semantics,
                "evolution": {
                    "algorithm": "genetic-evolution",
                    "islands": 4,
                    "population_per_island": 80,
                    "generations": generations,
                    "nominal_evaluations": evaluations,
                    "migration_every_generations": min(10, generations),
                    "migrants_per_island": 5,
                },
                "status": "AWAITING_CUSTOM_BLOCK_PARITY_AND_CFX_COMPILE",
            })

    expected = sum(row["evaluation_budget"] for row in campaign["hypothesis_search_spaces"])
    actual = sum(row["evolution"]["nominal_evaluations"] for row in jobs)
    if actual != expected or expected != sq["maximum_evaluations_global"]:
        raise ValueError(f"global evaluation budget mismatch: {actual} != {expected}")
    return {
        "schema_version": 1,
        "campaign_id": campaign["campaign_id"],
        "stage": "CHECK_5A_BUILD_PLAN_PERFORMANCE_BLIND",
        "preregistration_path": str(prereg_path),
        "preregistration_sha256": EXPECTED_PREREG_SHA256,
        "exit_contract_path": str(EXIT_CONTRACT.resolve()),
        "exit_contract_sha256": _sha(EXIT_CONTRACT),
        "performance_accessed": False,
        "holdout_accessed": False,
        "sqcli_executed": False,
        "job_count": len(jobs),
        "nominal_evaluations_global": actual,
        "exit_branch_policy": "FIX_EXIT_TEMPLATE_PER_JOB_AND_SPLIT_SEALED_GENERATIONS",
        "jobs": jobs,
        "authorization": {"compile_cfx": True, "execute_sqcli": False,
                          "paper": False, "live": False},
    }


def verify_plan(plan: dict[str, Any], *, require_history: bool = True) -> None:
    if (plan.get("job_count") != 18 or plan.get("nominal_evaluations_global") != 76800
            or plan.get("performance_accessed") is not False
            or plan.get("holdout_accessed") is not False
            or plan.get("sqcli_executed") is not False):
        raise ValueError("SQ build plan campaign contract failed")
    ids = [row["job_id"] for row in plan["jobs"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate SQ job id")
    totals: dict[str, int] = {}
    for job in plan["jobs"]:
        if job["future_periods_embargoed"] != ["validation", "oos", "holdout"]:
            raise ValueError("future period embargo missing")
        if len(job["numeric_axes"]) != 2 or job["resource"]["chart_timeframe"] not in {"M15", "D1"}:
            raise ValueError("job search-space contract failed")
        if (not job.get("exit_semantics", {}).get("stop")
                or not job.get("exit_semantics", {}).get("target")
                or job["exit_semantics"].get("max_bars", 0) < 1):
            raise ValueError("exact exit semantics missing")
        if require_history and not Path(job["resource"]["history_path"]).is_file():
            raise ValueError(f"SQ history missing: {job['resource']['history_path']}")
        totals[job["hypothesis_id"]] = totals.get(job["hypothesis_id"], 0) + job["evolution"]["nominal_evaluations"]
    expected = {16000, 10240, 9280}
    if set(totals.values()) != expected or sorted(totals.values()).count(16000) != 3:
        raise ValueError(f"per-hypothesis budget contract failed: {totals}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = compile_plan(args.preregistration)
    verify_plan(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": "PASS_CHECK_5A_BUILD_PLAN", "jobs": plan["job_count"],
                      "nominal_evaluations": plan["nominal_evaluations_global"],
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
