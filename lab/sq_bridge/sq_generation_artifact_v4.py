#!/usr/bin/env python3
"""Construeix evidència v4 de generació SQ exclusivament des de fitxers congelats."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from lab.sq_bridge.evidence_chain import verify as verify_chain
from lab.sq_bridge.temporal_split_contract_v4 import digest as temporal_digest, sq_periods

try:
    from lab.sq_bridge.sqx_extract import extract
    from lab.sq_bridge.sqx_to_ir import canonical_ir, validate_executable_ir
except ModuleNotFoundError:  # execució directa des de lab/sq_bridge
    from sqx_extract import extract
    from sqx_to_ir import canonical_ir, validate_executable_ir


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def _inventory(paths: list[Path], root: Path) -> tuple[list[dict], str]:
    rows = [{"path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}
            for path in paths]
    digest = hashlib.sha256("".join(
        f"{row['path']}:{row['sha256']}\n" for row in rows).encode()).hexdigest()
    return rows, digest


def _validate_project_chain(manifest: dict, methodology_path: Path,
                            campaign_id: str, source_hypothesis_ids: list[str]) -> dict:
    path_value = manifest.get("evidence_chain_path")
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("El manifest SQ no referencia la cadena v4")
    path = Path(path_value)
    if (not path.is_file() or manifest.get("evidence_chain_sha256") != _sha256(path)):
        raise ValueError("La cadena v4 del manifest no coincideix amb el seu hash")
    chain = json.loads(path.read_text())
    result = verify_chain(chain, methodology_path)
    if (not result.get("valid") or result.get("terminal")
            or result.get("next_stage") != "sq_generation"
            or result.get("promotable") is not True):
        raise ValueError("La cadena v4 ja no autoritza generacio SQ")
    if (manifest.get("campaign_id") != campaign_id
            or chain.get("campaign_id") != campaign_id
            or manifest.get("source_hypothesis_id") != chain.get("hypothesis_id")
            or source_hypothesis_ids != [chain.get("hypothesis_id")]):
        raise ValueError("La filiacio campanya/hipotesi del projecte SQ no coincideix")
    receipts = chain.get("receipts") or []
    if (len(receipts) != 2
            or manifest.get("market_preflight_receipt_sha256")
                != receipts[0].get("receipt_sha256")
            or manifest.get("hypothesis_screen_receipt_sha256")
                != receipts[1].get("receipt_sha256")):
        raise ValueError("Els rebuts prerequisit del manifest SQ no coincideixen")
    profiles = {
        "d1_breakout": "eurusd_d1_breakout_v4",
        "d1_momentum": "eurusd_d1_momentum_v4",
        "d1_shock_reversion": "eurusd_d1_shock_reversion_v4",
    }
    source_id = manifest.get("source_hypothesis_id")
    if manifest.get("market") == "EURUSD" and source_id in profiles:
        contract_path = Path(str(manifest.get("temporal_split_contract_path", "")))
        if not contract_path.is_file():
            raise ValueError("El contracte temporal SQ no existeix")
        contract = json.loads(contract_path.read_text())
        screen_path = Path(receipts[1]["artifact"])
        screen = json.loads(screen_path.read_text())
        trace_path = Path(str(screen.get("hypothesis_screen_trace_path", "")))
        trace_path = (trace_path if trace_path.is_absolute()
                      else screen_path.resolve().parent / trace_path)
        trace = json.loads(trace_path.read_text()) if trace_path.is_file() else {}
        if (manifest.get("search_profile") != profiles[source_id]
                or manifest.get("temporal_split_contract_sha256")
                    != temporal_digest(contract)
                or manifest.get("temporal_source_sha256") != contract.get("source_sha256")
                or manifest.get("periods") != sq_periods(contract)
                or screen.get("hypothesis_screen_trace_sha256") != _sha256(trace_path)
                or trace.get("temporal_contract_sha256") != temporal_digest(contract)):
            raise ValueError("La filiacio temporal/perfil del projecte SQ no coincideix")
    return {"path": str(path), "sha256": _sha256(path)}


def build_artifact(*, campaign_id: str, source_hypothesis_ids: list[str],
                   databank_dir: Path, watchdog_status_path: Path,
                   project_cfx: Path, project_manifest_path: Path,
                   methodology_path: Path, output_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    manifest = json.loads(project_manifest_path.read_text())
    generation = methodology["sq_generation"]
    if methodology.get("schema_version") != 4:
        raise ValueError("Es requereix methodology v4")
    if not campaign_id.strip():
        raise ValueError("campaign_id buit")
    if (not source_hypothesis_ids
            or any(not isinstance(value, str) or not value.strip()
                   for value in source_hypothesis_ids)
            or len(set(source_hypothesis_ids)) != len(source_hypothesis_ids)):
        raise ValueError("source_hypothesis_ids han de ser unics i no buits")
    chain_receipt = _validate_project_chain(
        manifest, methodology_path, campaign_id, source_hypothesis_ids)
    watchdog = json.loads(watchdog_status_path.read_text())
    attempted = watchdog.get("generated")
    if (not isinstance(attempted, int) or isinstance(attempted, bool)
            or not 1 <= attempted <= generation["maximum_attempts"]):
        raise ValueError("El watchdog no prova un recompte d'intents valid")
    if manifest.get("methodology_id") != methodology.get("methodology_id"):
        raise ValueError("El manifest no pertany a aquesta metodologia")
    if manifest.get("generation_type") != generation["search_method"].replace("_", "-"):
        raise ValueError("El projecte no usa la cerca genetica preregistrada")
    if manifest.get("holdout_sealed") is not True:
        raise ValueError("El holdout del projecte no consta segellat")
    if watchdog.get("project") != manifest.get("project_name"):
        raise ValueError("El snapshot del watchdog no correspon al projecte")
    if watchdog.get("state") != "BUDGET_REACHED" or watchdog.get("reason") not in {
            "ATTEMPT_BUDGET", "ACCEPTED_TARGET", "WALL_TIME_BUDGET"}:
        raise ValueError("L'execucio SQ no consta finalitzada per un gate congelat")
    if manifest.get("output_sha256") != _sha256(project_cfx):
        raise ValueError("El hash del CFX no coincideix amb el manifest")
    budget = manifest.get("attempt_budget")
    if (not isinstance(budget, int) or isinstance(budget, bool)
            or attempted > budget or budget > generation["maximum_attempts"]):
        raise ValueError("L'execucio supera el pressupost congelat del projecte")

    sqx_paths = sorted(databank_dir.rglob("*.sqx"))
    if not sqx_paths:
        raise ValueError("El databank congelat no conte cap SQX")
    inventory, inventory_sha256 = _inventory(sqx_paths, databank_dir)
    watchdog_inventory = watchdog.get("artifacts")
    if (not isinstance(watchdog_inventory, list)
            or [{"path": row.get("path"), "sha256": row.get("sha256")}
                for row in watchdog_inventory] != inventory):
        raise ValueError("El databank actual no coincideix amb el snapshot final del watchdog")
    contracts: dict[str, tuple[Path, dict]] = {}
    for path in sqx_paths:
        contract = extract(path)
        candidate_id = contract.get("strategy_name")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError(f"SQX sense StrategyName: {path}")
        if candidate_id in contracts:
            raise ValueError(f"StrategyName duplicat: {candidate_id}")
        if not contract["supported"]:
            raise ValueError(
                f"SQX no traduible {candidate_id}: {contract['unsupported_nodes_or_formulas']}")
        count = contract["maximum_entry_conditions"]
        if not 1 <= count <= generation["max_rules"]:
            raise ValueError(
                f"Complexitat fora del contracte {candidate_id}: {count}")
        try:
            validate_executable_ir(canonical_ir(contract))
        except ValueError as error:
            raise ValueError(
                f"SQX no executable amb risc controlat {candidate_id}: {error}") from error
        expected_symbol = manifest.get("sq_symbol")
        expected_timeframe = manifest.get("timeframe")
        if expected_symbol and contract["market"]["symbol"] != expected_symbol:
            raise ValueError(f"Mercat SQX inesperat: {candidate_id}")
        if expected_timeframe and contract["market"]["timeframe"] != expected_timeframe:
            raise ValueError(f"Timeframe SQX inesperat: {candidate_id}")
        contracts[candidate_id] = (path, contract)

    output_base = output_path.resolve().parent
    candidate_ids = sorted(contracts)
    artifact = {
        "schema_version": 1,
        "stage": "sq_generation",
        "campaign_id": campaign_id,
        "decision": "PASS",
        "candidate_ids": candidate_ids,
        "holdout_accessed": False,
        "evidence_class": "observed",
        "generator": "StrategyQuant",
        "search_method": generation["search_method"],
        "selection_policy": generation["selection_policy"],
        "attempted": attempted,
        "source_hypothesis_ids": sorted(source_hypothesis_ids),
        "selected_candidate_ids": candidate_ids,
        "candidate_artifact_paths": {
            key: _relative(contracts[key][0], output_base) for key in candidate_ids},
        "candidate_artifact_hashes": {
            key: contracts[key][1]["source_sha256"] for key in candidate_ids},
        "rules_per_candidate": {
            key: contracts[key][1]["maximum_entry_conditions"] for key in candidate_ids},
        "entry_condition_counts_per_candidate": {
            key: contracts[key][1]["entry_condition_counts"] for key in candidate_ids},
        "translation_status_per_candidate": {
            key: contracts[key][1]["translation_status"] for key in candidate_ids},
        "trade_execution_normalized_per_candidate": {
            key: True for key in candidate_ids},
        "stop_loss_required_satisfied_per_candidate": {
            key: True for key in candidate_ids},
        "sq_config_sha256": _sha256(project_cfx),
        "sq_project_manifest_path": _relative(project_manifest_path, output_base),
        "sq_project_manifest_sha256": _sha256(project_manifest_path),
        "sq_watchdog_status_path": _relative(watchdog_status_path, output_base),
        "sq_watchdog_status_sha256": _sha256(watchdog_status_path),
        "databank_path": _relative(databank_dir, output_base),
        "databank_candidate_count": len(inventory),
        "databank_inventory_sha256": inventory_sha256,
        "databank_frozen": True,
        "future_periods_accessed": False,
        "prerequisite_evidence_chain_path": _relative(
            Path(chain_receipt["path"]), output_base),
        "prerequisite_evidence_chain_sha256": chain_receipt["sha256"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--source-hypothesis-id", action="append", required=True)
    parser.add_argument("--databank-dir", required=True, type=Path)
    parser.add_argument("--watchdog-status", required=True, type=Path)
    parser.add_argument("--project-cfx", required=True, type=Path)
    parser.add_argument("--project-manifest", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    artifact = build_artifact(
        campaign_id=args.campaign_id,
        source_hypothesis_ids=args.source_hypothesis_id,
        databank_dir=args.databank_dir,
        watchdog_status_path=args.watchdog_status,
        project_cfx=args.project_cfx,
        project_manifest_path=args.project_manifest,
        methodology_path=args.methodology,
        output_path=args.output,
    )
    print(json.dumps({"candidate_ids": artifact["candidate_ids"],
                      "rules_per_candidate": artifact["rules_per_candidate"]}, indent=2))


if __name__ == "__main__":
    main()
