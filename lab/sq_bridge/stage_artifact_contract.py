#!/usr/bin/env python3
"""Strict, deterministic contracts for Alquimia v3 stage evidence artifacts."""
from __future__ import annotations

from typing import Any


def _at_least(value: Any, threshold: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= threshold


def _at_most(value: Any, threshold: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value <= threshold


def _ids(value: Any) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return sorted(set(value))


def validate_stage_artifact(stage: str, artifact: dict, receipt: dict, methodology: dict,
                            campaign_id: str, provenance: str) -> list[str]:
    errors: list[str] = []
    prefix = f"STAGE_ARTIFACT:{stage}"
    if artifact.get("schema_version") != 1:
        errors.append(f"{prefix}:SCHEMA_VERSION")
    if artifact.get("stage") != stage:
        errors.append(f"{prefix}:STAGE")
    if artifact.get("campaign_id") != campaign_id:
        errors.append(f"{prefix}:CAMPAIGN")
    if artifact.get("decision") != receipt.get("decision"):
        errors.append(f"{prefix}:DECISION")
    artifact_ids = _ids(artifact.get("candidate_ids"))
    if artifact_ids is None or artifact_ids != receipt.get("candidate_ids", []):
        errors.append(f"{prefix}:CANDIDATES")
    if bool(artifact.get("holdout_accessed", False)) != bool(receipt.get("holdout_accessed", False)):
        errors.append(f"{prefix}:HOLDOUT")
    expected_class = "synthetic_control" if provenance == "synthetic_control" else "observed"
    if artifact.get("evidence_class") != expected_class:
        errors.append(f"{prefix}:EVIDENCE_CLASS")
    if provenance == "synthetic_control" and artifact.get("control_purpose") != "pipeline_wiring_only":
        errors.append(f"{prefix}:CONTROL_PURPOSE")
    if receipt.get("decision") != "PASS":
        return errors

    temporal = methodology["temporal_validation"]
    robust = methodology["robustness"]
    small = methodology["small_account"]
    checks: dict[str, bool]
    if stage == "market_preflight":
        checks = {
            "MARKET_EXECUTABLE": artifact.get("market_executable") is True,
            "DATA_GATE": artifact.get("data_gate") == "PASS",
            "OSTIUM_PAIR": bool(artifact.get("ostium_pair_id")),
        }
    elif stage == "discovery":
        checks = {
            "SQ_SOURCE": artifact.get("generator") == "StrategyQuant",
            "ATTEMPTED": _at_least(artifact.get("attempted"), 1),
            "SELECTED": _ids(artifact.get("selected_candidate_ids")) == receipt.get("candidate_ids", []),
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
    elif stage == "temporal_validation":
        checks = {
            "OOS_TRADES": _at_least(artifact.get("oos_trades"), temporal["minimum_trades_oos"]),
            "POSITIVE_WINDOWS": _at_least(artifact.get("positive_windows_ratio"), temporal["minimum_positive_windows_ratio"]),
            "OOS_PF": _at_least(artifact.get("oos_profit_factor"), temporal["minimum_oos_profit_factor"]),
            "OOS_DD": _at_most(artifact.get("oos_drawdown_pct"), temporal["maximum_oos_drawdown_pct"]),
            "EXPECTANCY_DECAY": _at_most(artifact.get("train_oos_expectancy_decay_pct"), temporal["maximum_train_oos_expectancy_decay_pct"]),
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
    elif stage == "robustness":
        checks = {
            "MC_RUNS": _at_least(artifact.get("monte_carlo_runs"), robust["monte_carlo_runs"]),
            "MC_PROFITABLE": _at_least(artifact.get("profitable_monte_carlo_ratio"), robust["minimum_profitable_monte_carlo_ratio"]),
            "PARAMETER_PERTURBATION": artifact.get("parameter_perturbation_pct") == robust["parameter_perturbation_pct"],
            "COST_STRESS": _at_least(artifact.get("cost_stress_multiplier"), robust["cost_stress_multiplier"]),
            "STRESS_PF": _at_least(artifact.get("stress_profit_factor"), robust["minimum_stress_profit_factor"]),
            "LIQUIDATION": _at_most(artifact.get("liquidation_probability"), robust["maximum_liquidation_probability"]),
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
    elif stage == "small_account_economics":
        checks = {
            "CAPITAL": artifact.get("capital_usdc") == small["canonical_capital_usdc"],
            "EXPECTANCY": _at_least(artifact.get("net_expectancy_usdc"), small["minimum_net_expectancy_usdc"]),
            "NET_PF": _at_least(artifact.get("net_profit_factor"), small["minimum_net_profit_factor"]),
            "RISK": _at_most(artifact.get("risk_per_trade_pct"), small["maximum_risk_per_trade_pct"]),
            "MARGIN": _at_most(artifact.get("portfolio_margin_pct"), small["maximum_portfolio_margin_pct"]),
            "RESERVE": _at_least(artifact.get("reserve_pct"), small["minimum_reserve_pct"]),
            "LEVERAGE": artifact.get("selected_leverage") in small["leverage_grid"],
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
    elif stage == "python_translation":
        checks = {
            "EXACT": artifact.get("translation_exact") is True and receipt.get("translation_exact") is True,
            "SUPPORTED": artifact.get("supported_subset") is True,
            "SQX_HASH": isinstance(artifact.get("sqx_sha256"), str) and len(artifact["sqx_sha256"]) == 64,
            "IR_HASH": isinstance(artifact.get("canonical_ir_sha256"), str) and len(artifact["canonical_ir_sha256"]) == 64,
        }
    elif stage == "parity":
        checks = {
            "PASS": artifact.get("parity_pass") is True and receipt.get("parity_pass") is True,
            "SIGNALS": artifact.get("signal_match_rate") == 1.0,
            "TRADES": artifact.get("trade_match_rate") == 1.0,
            "CANDLE_COVERAGE": _at_least(artifact.get("candle_coverage_pct"), 95.0),
            "PNL_CORRELATION": _at_least(artifact.get("pnl_correlation"), 0.99),
        }
    elif stage == "paper":
        checks = {
            "MODE": artifact.get("mode") == "paper",
            "PROBE": artifact.get("paper_probe_configured") is True,
            "LIVE_FALSE": artifact.get("live_authorized") is False,
        }
    else:
        checks = {"KNOWN_STAGE": False}
    errors.extend(f"{prefix}:{name}" for name, passed in checks.items() if not passed)
    return errors
