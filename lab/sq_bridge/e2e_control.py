#!/usr/bin/env python3
"""Generate a deterministic, non-promotable control for the Alquimia v3 pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab.sq_bridge.evidence_chain import append_receipt, new_chain, verify


CAMPAIGN = "alquimia-v3-strict-control"
CANDIDATE = "synthetic-sqx-control-001"


def payload(stage: str, candidate_ids: list[str], holdout: bool) -> dict:
    common = {
        "schema_version": 1,
        "stage": stage,
        "campaign_id": CAMPAIGN,
        "decision": "PASS",
        "candidate_ids": candidate_ids,
        "holdout_accessed": holdout,
        "evidence_class": "synthetic_control",
        "control_purpose": "pipeline_wiring_only",
    }
    fields = {
        "market_preflight": {"market_executable": True, "data_gate": "PASS", "ostium_pair_id": "control-pair",
                             "performance_accessed": False, "historical_coverage_pass": True,
                             "historical_expected_observations": 100,
                             "historical_complete_observations": 95,
                             "historical_overall_coverage_ratio": .95,
                             "historical_minimum_period_coverage_ratio": .85,
                             "historical_period_coverage": {"train-a": .85, "train-b": .95},
                             "source_mapping_pass": True, "proxy_candle_coverage_pct": 99,
                             "return_correlation": .999, "execution_economics_complete": True,
                             "future_periods_sealed": True, "campaign_config_sha256": "c" * 64},
        "discovery": {"generator": "StrategyQuant", "attempted": 1, "selected_candidate_ids": candidate_ids},
        "hypothesis_screen": {"generator": "deterministic_pre_sq_screen", "attempted": 1,
                              "selected_hypothesis_ids": ["hypothesis-control"],
                              "stable_region_pass": True, "all_cost_scenarios_applied": True,
                              "train_only": True},
        "sq_generation": {"generator": "StrategyQuant", "attempted": 1,
                          "selected_candidate_ids": candidate_ids,
                          "candidate_artifact_hashes": {candidate: "a" * 64
                                                        for candidate in candidate_ids},
                          "sq_config_sha256": "b" * 64},
        "temporal_validation": {"oos_trades": 30, "positive_windows_ratio": 0.6, "oos_profit_factor": 1.15,
                                "oos_drawdown_pct": 20, "train_oos_expectancy_decay_pct": 50},
        "robustness": {"monte_carlo_runs": 1000, "profitable_monte_carlo_ratio": 0.7,
                       "parameter_perturbation_pct": 10, "cost_stress_multiplier": 2,
                       "stress_profit_factor": 1.05, "liquidation_probability": 0.001},
        "small_account_economics": {"capital_usdc": 200, "net_expectancy_usdc": 0.1,
                                    "net_profit_factor": 1.1, "risk_per_trade_pct": 1.5,
                                    "portfolio_margin_pct": 35, "reserve_pct": 40, "selected_leverage": 5},
        "python_translation": {"translation_exact": True, "supported_subset": True,
                               "sqx_sha256": "a" * 64, "canonical_ir_sha256": "b" * 64},
        "parity": {"parity_pass": True, "signal_match_rate": 1.0, "trade_match_rate": 1.0,
                   "candle_coverage_pct": 95, "pnl_correlation": 0.99},
        "paper": {"mode": "paper", "paper_probe_configured": True, "live_authorized": False},
    }
    common.update(fields[stage])
    return common


def generate(methodology_path: Path, output_dir: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    output_dir.mkdir(parents=True, exist_ok=True)
    chain = new_chain(methodology_path, CAMPAIGN, "wiring-control", "SYNTHETIC", "synthetic_control")
    ids: list[str] = []
    for index, stage in enumerate(methodology["stages"], 1):
        if stage in {"discovery", "sq_generation"}:
            ids = [CANDIDATE]
        holdout = stage in {"python_translation", "parity", "paper"}
        artifact = output_dir / f"{index:02d}_{stage}.json"
        artifact.write_text(json.dumps(payload(stage, ids, holdout), indent=2, sort_keys=True) + "\n")
        chain = append_receipt(
            chain, methodology, stage, artifact, "PASS", ids,
            holdout_accessed=holdout,
            translation_exact=True if stage == "python_translation" else None,
            parity_pass=True if stage == "parity" else None,
        )
    chain_path = output_dir / "chain.json"
    chain_path.write_text(json.dumps(chain, indent=2, sort_keys=True) + "\n")
    result = verify(chain, methodology_path)
    verification_path = output_dir / "verification.json"
    verification_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not (result["valid"] and result["operational_control_complete"]):
        raise RuntimeError(f"control failed: {result['errors']}")
    if result["promotable"] or result["paper_ready"] or result["live_authorized"]:
        raise RuntimeError("synthetic control escaped its non-promotable boundary")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--methodology", type=Path, default=Path(__file__).with_name("methodology_v3.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.methodology, args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
