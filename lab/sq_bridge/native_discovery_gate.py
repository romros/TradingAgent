#!/usr/bin/env python3
"""Freeze and semantically gate one native Alquimia SQ discovery databank."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from lab.sq_bridge.discovery_inventory import inventory
from lab.sq_bridge.sqx_extract import extract
from lab.sq_bridge.structural_hypothesis_gate import sweep_reclaim


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def freeze(source: Path, destination: Path) -> list[Path]:
    sqx = sorted(source.glob("*.sqx"))
    if not sqx:
        raise ValueError(f"NO_SQX: {source}")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"FREEZE_DESTINATION_NOT_EMPTY: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    for path in sqx:
        shutil.copy2(path, destination / path.name)
    return sorted(destination.glob("*.sqx"))


def process(source: Path, output_dir: Path, project_cfx: Path,
            project_manifest: Path) -> dict:
    frozen = output_dir / "frozen_databank"
    paths = freeze(source, frozen)
    inventory_path = output_dir / "inventory.json"
    _write(inventory_path, inventory(frozen, project_cfx, project_manifest))

    evaluations = []
    for path in paths:
        contract_path = output_dir / "contracts" / f"{path.stem}.json"
        gate_path = output_dir / "structural_gates" / f"{path.stem}.json"
        try:
            contract = extract(path)
            _write(contract_path, contract)
            gate = sweep_reclaim(contract)
        except (KeyError, ValueError) as exc:
            gate = {
                "strategy": path.stem,
                "hypothesis": "xau-h4-sweep-reclaim-v4",
                "passed": False,
                "reasons": [f"CONTRACT_EXTRACTION_ERROR:{type(exc).__name__}:{exc}"],
                "translation_status": "UNSUPPORTED",
            }
        _write(gate_path, gate)
        evaluations.append(gate)

    passed = sorted(row["strategy"] for row in evaluations if row["passed"])
    rejected = sorted(row["strategy"] for row in evaluations if not row["passed"])
    summary = {
        "schema_version": 1,
        "stage": "discovery",
        "hypothesis": "xau-h4-sweep-reclaim-v4",
        "structural_contract": "signal-bar-shift-1_vs_prior-extreme-shift-2_same-period-v1",
        "gate_implementation_sha256": hashlib.sha256(
            Path(__file__).with_name("structural_hypothesis_gate.py").read_bytes()
        ).hexdigest(),
        "source_candidate_count": len(paths),
        "structural_pass_count": len(passed),
        "candidate_ids": passed,
        "rejected_candidate_ids": rejected,
        "decision": "PASS" if passed else "REJECT",
        "holdout_accessed": False,
        "inventory": str(inventory_path),
        "inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        "evaluations": evaluations,
    }
    _write(output_dir / "discovery_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--project-cfx", type=Path, required=True)
    parser.add_argument("--project-manifest", type=Path, required=True)
    args = parser.parse_args()
    result = process(args.source, args.output_dir, args.project_cfx, args.project_manifest)
    print(json.dumps({key: result[key] for key in (
        "source_candidate_count", "structural_pass_count", "candidate_ids", "decision"
    )}, indent=2))


if __name__ == "__main__":
    main()
