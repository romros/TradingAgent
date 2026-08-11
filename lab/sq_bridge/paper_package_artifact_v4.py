#!/usr/bin/env python3
"""Empaqueta per paper exactament el candidat v4 validat, sense signer ni ordres."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROLES = ("market_preflight", "small_account_economics", "final_holdout_validation",
         "python_translation", "parity")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def _resolve(value: str, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def _load(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON no objecte: {path}")
    return value


def _validated_sources(paths: dict[str, Path], campaign_id: str,
                       candidate_id: str) -> dict[str, dict]:
    if set(paths) != set(ROLES):
        raise ValueError("Falten etapes font del paquet paper")
    sources = {role: _load(path) for role, path in paths.items()}
    for role, value in sources.items():
        if (value.get("stage") != role or value.get("campaign_id") != campaign_id
                or value.get("decision") != "PASS"):
            raise ValueError(f"Etapa font no aprovada o aliena: {role}")
        if role != "market_preflight" and value.get("candidate_ids") != [candidate_id]:
            raise ValueError(f"Candidate lineage mismatch: {role}")
    if sources["market_preflight"].get("candidate_ids") != []:
        raise ValueError("Market preflight no pot crear candidats")
    if sources["final_holdout_validation"].get("holdout_evaluation_count") != 1:
        raise ValueError("Holdout final no valid")
    if sources["python_translation"].get("translation_exact") is not True:
        raise ValueError("Traduccio no exacta")
    if sources["parity"].get("parity_pass") is not True:
        raise ValueError("Paritat no aprovada")
    return sources


def build_artifact(*, campaign_id: str, candidate_id: str,
                   source_artifact_paths: dict[str, Path], config_path: Path,
                   artifact_path: Path) -> dict:
    sources = _validated_sources(source_artifact_paths, campaign_id, candidate_id)
    translation_path = source_artifact_paths["python_translation"]
    translation = sources["python_translation"]
    ir_path = _resolve(translation["canonical_ir_path"], translation_path.resolve().parent)
    if _sha(ir_path) != translation.get("canonical_ir_sha256"):
        raise ValueError("IR traduït absent o manipulat")
    parity_path = source_artifact_paths["parity"]
    parity = sources["parity"]
    report_path = _resolve(parity["parity_report_path"], parity_path.resolve().parent)
    if _sha(report_path) != parity.get("parity_report_sha256"):
        raise ValueError("Report de paritat absent o manipulat")
    market = sources["market_preflight"]
    small = sources["small_account_economics"]
    base = config_path.resolve().parent
    small_path = source_artifact_paths["small_account_economics"].resolve()
    cost_model_path = _resolve(small["cost_model_path"], small_path.parent).resolve()
    frozen_costs = _load(cost_model_path)
    if (_sha(cost_model_path) != small.get("cost_model_sha256")
            or frozen_costs.get("decision") != "PASS_COSTS_FROZEN"
            or frozen_costs.get("costs_frozen") is not True):
        raise ValueError("Model de costos congelat absent o manipulat")
    config = {
        "schema_version": 2,
        "package_type": "alquimia_paper_candidate",
        "campaign_id": campaign_id,
        "candidate_id": candidate_id,
        "capital_usdc": 200,
        "mode": "paper",
        "live_authorized": False,
        "signer_enabled": False,
        "ostium_pair_id": market["ostium_pair_id"],
        "selected_leverage": small["selected_leverage"],
        "venue_max_leverage": small["venue_max_leverage"],
        "risk_per_trade_pct": small["risk_per_trade_pct"],
        "sizing_policy": "risk_budget_over_runtime_initial_stop_capped_by_validated_notional",
        "dynamic_stop_sizing": True,
        "portfolio_margin_pct": small["portfolio_margin_pct"],
        "reserve_pct": small["reserve_pct"],
        "position_notional_usdc": small["position_notional_usdc"],
        "minimum_position_notional_usdc": small["minimum_position_notional_usdc"],
        "maximum_position_notional_usdc": small["maximum_position_notional_usdc"],
        "venue_minimum_notional_usdc": small["venue_minimum_notional_usdc"],
        "collateral_usdc": small["collateral_usdc"],
        "entry_cost_buffer_usdc": small["entry_cost_buffer_usdc"],
        "capital_committed_usdc": small["capital_committed_usdc"],
        "reserve_usdc": small["reserve_usdc"],
        "stop_loss_required": small["stop_loss_required"],
        "stop_distance_pct": small["stop_distance_pct"],
        "cost_model_path": _relative(cost_model_path, base),
        "cost_model_sha256": _sha(cost_model_path),
        "strategy_ir_path": _relative(ir_path, base),
        "strategy_ir_sha256": _sha(ir_path),
        "parity_report_path": _relative(report_path, base),
        "parity_report_sha256": _sha(report_path),
        "source_artifacts": {
            role: {"path": _relative(source_artifact_paths[role], base),
                   "sha256": _sha(source_artifact_paths[role])}
            for role in ROLES},
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    artifact_base = artifact_path.resolve().parent
    artifact = {
        "schema_version": 1, "stage": "paper", "campaign_id": campaign_id,
        "decision": "PASS", "candidate_ids": [candidate_id],
        "holdout_accessed": False, "evidence_class": "observed",
        "mode": "paper", "paper_probe_configured": True, "live_authorized": False,
        "paper_config_path": _relative(config_path, artifact_base),
        "paper_config_sha256": _sha(config_path),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def verify_package(config: dict, config_path: Path) -> bool:
    try:
        if (config.get("schema_version") != 2
                or config.get("package_type") != "alquimia_paper_candidate"
                or config.get("capital_usdc") != 200 or config.get("mode") != "paper"
                or config.get("live_authorized") is not False
                or config.get("signer_enabled") is not False
                or not config.get("ostium_pair_id")):
            return False
        base = config_path.resolve().parent
        refs = config.get("source_artifacts")
        if not isinstance(refs, dict) or set(refs) != set(ROLES):
            return False
        paths = {}
        for role, ref in refs.items():
            if not isinstance(ref, dict):
                return False
            path = _resolve(ref.get("path", ""), base)
            if not path.is_file() or _sha(path) != ref.get("sha256"):
                return False
            paths[role] = path
        sources = _validated_sources(
            paths, config["campaign_id"], config["candidate_id"])
        market, small = sources["market_preflight"], sources["small_account_economics"]
        small_path = paths["small_account_economics"].resolve()
        cost_model = _resolve(config.get("cost_model_path", ""), base).resolve()
        expected_cost_model = _resolve(
            small.get("cost_model_path", ""), small_path.parent).resolve()
        if (cost_model != expected_cost_model or not cost_model.is_file()
                or _sha(cost_model) != config.get("cost_model_sha256")
                or config.get("cost_model_sha256") != small.get("cost_model_sha256")):
            return False
        frozen_costs = _load(cost_model)
        if (frozen_costs.get("decision") != "PASS_COSTS_FROZEN"
                or frozen_costs.get("costs_frozen") is not True):
            return False
        expected = {
            "ostium_pair_id": market["ostium_pair_id"],
            "selected_leverage": small["selected_leverage"],
            "venue_max_leverage": small["venue_max_leverage"],
            "risk_per_trade_pct": small["risk_per_trade_pct"],
            "sizing_policy": "risk_budget_over_runtime_initial_stop_capped_by_validated_notional",
            "dynamic_stop_sizing": True,
            "portfolio_margin_pct": small["portfolio_margin_pct"],
            "reserve_pct": small["reserve_pct"],
            "position_notional_usdc": small["position_notional_usdc"],
            "minimum_position_notional_usdc": small["minimum_position_notional_usdc"],
            "maximum_position_notional_usdc": small["maximum_position_notional_usdc"],
            "venue_minimum_notional_usdc": small["venue_minimum_notional_usdc"],
            "collateral_usdc": small["collateral_usdc"],
            "entry_cost_buffer_usdc": small["entry_cost_buffer_usdc"],
            "capital_committed_usdc": small["capital_committed_usdc"],
            "reserve_usdc": small["reserve_usdc"],
            "stop_loss_required": small["stop_loss_required"],
            "stop_distance_pct": small["stop_distance_pct"],
        }
        if any(config.get(key) != value for key, value in expected.items()):
            return False
        translation = sources["python_translation"]
        ir = _resolve(config.get("strategy_ir_path", ""), base)
        parity_report = _resolve(config.get("parity_report_path", ""), base)
        return (ir.is_file() and _sha(ir) == config.get("strategy_ir_sha256")
                == translation.get("canonical_ir_sha256")
                and parity_report.is_file()
                and _sha(parity_report) == config.get("parity_report_sha256")
                == sources["parity"].get("parity_report_sha256"))
    except (KeyError, OSError, TypeError, ValueError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    for role in ROLES:
        parser.add_argument(f"--{role.replace('_', '-')}", required=True, type=Path)
    parser.add_argument("--config-output", required=True, type=Path)
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    paths = {role: getattr(args, role) for role in ROLES}
    result = build_artifact(
        campaign_id=args.campaign_id, candidate_id=args.candidate_id,
        source_artifact_paths=paths, config_path=args.config_output,
        artifact_path=args.artifact_output)
    print(json.dumps({"decision": result["decision"],
                      "paper_config_sha256": result["paper_config_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
