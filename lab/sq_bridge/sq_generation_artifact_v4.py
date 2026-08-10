#!/usr/bin/env python3
"""Construeix evidència v4 de generació SQ exclusivament des de fitxers congelats."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

try:
    from lab.sq_bridge.sqx_extract import extract
except ModuleNotFoundError:  # execució directa des de lab/sq_bridge
    from sqx_extract import extract


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def build_artifact(*, campaign_id: str, source_hypothesis_ids: list[str], attempted: int,
                   databank_dir: Path, project_cfx: Path, project_manifest_path: Path,
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
    if (not isinstance(attempted, int) or isinstance(attempted, bool)
            or not 1 <= attempted <= generation["maximum_attempts"]):
        raise ValueError("attempted fora del pressupost metodologic")
    if manifest.get("methodology_id") != methodology.get("methodology_id"):
        raise ValueError("El manifest no pertany a aquesta metodologia")
    if manifest.get("generation_type") != generation["search_method"].replace("_", "-"):
        raise ValueError("El projecte no usa la cerca genetica preregistrada")
    if manifest.get("holdout_sealed") is not True:
        raise ValueError("El holdout del projecte no consta segellat")
    if manifest.get("output_sha256") != _sha256(project_cfx):
        raise ValueError("El hash del CFX no coincideix amb el manifest")
    budget = manifest.get("attempt_budget")
    if (not isinstance(budget, int) or isinstance(budget, bool)
            or attempted > budget or budget > generation["maximum_attempts"]):
        raise ValueError("L'execucio supera el pressupost congelat del projecte")

    sqx_paths = sorted(databank_dir.glob("*.sqx"))
    if not sqx_paths:
        raise ValueError("El databank congelat no conte cap SQX")
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
        "sq_config_sha256": _sha256(project_cfx),
        "sq_project_manifest_path": _relative(project_manifest_path, output_base),
        "sq_project_manifest_sha256": _sha256(project_manifest_path),
        "databank_frozen": True,
        "future_periods_accessed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--source-hypothesis-id", action="append", required=True)
    parser.add_argument("--attempted", required=True, type=int)
    parser.add_argument("--databank-dir", required=True, type=Path)
    parser.add_argument("--project-cfx", required=True, type=Path)
    parser.add_argument("--project-manifest", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    artifact = build_artifact(
        campaign_id=args.campaign_id,
        source_hypothesis_ids=args.source_hypothesis_id,
        attempted=args.attempted,
        databank_dir=args.databank_dir,
        project_cfx=args.project_cfx,
        project_manifest_path=args.project_manifest,
        methodology_path=args.methodology,
        output_path=args.output,
    )
    print(json.dumps({"candidate_ids": artifact["candidate_ids"],
                      "rules_per_candidate": artifact["rules_per_candidate"]}, indent=2))


if __name__ == "__main__":
    main()
