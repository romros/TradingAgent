#!/usr/bin/env python3
"""Comprova que una release de l'expert conserva les acceptacions congelades."""

from __future__ import annotations

import argparse
import json
import unittest
from pathlib import Path

from benchmark_reality_transfer import benchmark
from observation_to_reality import assess_observation
from sq_coverage import report as coverage_report


ROOT = Path(__file__).resolve().parents[2]


def gate(release: dict) -> dict:
    acceptance = release["acceptance"]
    battle_path = ROOT / acceptance["reality_battle_suite"]
    blind_path = ROOT / acceptance["blind_case"]
    battle = benchmark(json.loads(battle_path.read_text(encoding="utf-8")))
    blind = json.loads(blind_path.read_text(encoding="utf-8"))
    observation = json.loads((ROOT / blind["observation"]).read_text(encoding="utf-8"))
    blind_result = assess_observation(observation)
    discovered_tests = unittest.defaultTestLoader.discover(str(ROOT / "academia/tests")).countTestCases()
    coverage = json.loads((ROOT / "academia/packages/strategyquant/coverage.json").read_text())
    tested_coverage = coverage_report(coverage, minimum="tested")
    required_boundaries = {
        "improver_slpt_only_structural_proof",
        "random_vs_genetic_equal_attempt_result",
        "source_code_export_and_target_engine_parity",
        "paper_trading_and_live_execution_out_of_scope",
    }
    checks = {
        "battle_score": battle["score"] >= acceptance["minimum_battle_score"],
        "battle_all_passed": battle["passed"],
        "blind_decision": blind_result["decision"] == acceptance["blind_expected_decision"] == blind["expected_decision"],
        "blind_metrics_verified": blind_result["metric_consistency_verified"],
        "unit_test_inventory": discovered_tests >= acceptance["minimum_unit_tests"],
        "boundaries_preserved": required_boundaries.issubset(set(release.get("open_boundaries", []))),
        "live_not_authorized": any("live" in item for item in release.get("open_boundaries", [])),
        "all_capabilities_tested": tested_coverage["coverage_ratio"] == 1,
    }
    return {
        "release": release["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "battle_score": battle["score"],
        "blind_actual": blind_result["decision"],
        "discovered_tests": discovered_tests,
        "tested_capability_coverage": tested_coverage,
        "limits": "El recompte no substitueix executar els tests. El gate no valida rendibilitat ni executa trading.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    args = parser.parse_args()
    result = gate(json.loads(args.release.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
