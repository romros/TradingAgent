#!/usr/bin/env python3
"""Verify terminal lineage for crypto intraday compression v18."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path): return json.loads(path.read_text())
def sha(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build(config_path: Path, development_path: Path, validation_path: Path) -> dict:
    config, development, validation = map(load, (config_path, development_path, validation_path))
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if development["config_sha256"] != config_hash or validation["config_sha256"] != config_hash:
        raise ValueError("CONFIG_LINEAGE_MISMATCH")
    if development["source_sha256"] != validation["source_sha256"]:
        raise ValueError("SOURCE_LINEAGE_MISMATCH")
    if not development["stable_candidate_ids"] or not development["topology_selected_representatives"]:
        raise ValueError("DEVELOPMENT_NOT_PROMOTABLE_TO_VALIDATION")
    if validation["decision"] != "REJECT_TEMPORAL_VALIDATION" or validation["passing_candidate_ids"]:
        raise ValueError("VALIDATION_NOT_TERMINAL_REJECTION")
    if development.get("validation_accessed") or development.get("holdout_accessed") or validation.get("holdout_accessed"):
        raise ValueError("SEALED_PERIOD_CONTRACT_BROKEN")
    paths = (config_path, development_path, validation_path)
    return {"schema_version": 1, "checkpoint_id": "crypto-intraday-compression-v18-terminal",
        "source_sha256": development["source_sha256"], "points_evaluated": development["points_evaluated"],
        "development_passes": development["point_gate_passes"],
        "stable_candidate_ids": development["stable_candidate_ids"],
        "selected_candidate_ids": [row["candidate_id"] for row in development["topology_selected_representatives"]],
        "validation_trade_counts": {row["candidate_id"]: row["metrics"]["stress"]["trades"] for row in validation["results"]},
        "artifact_sha256": {str(path): sha(path) for path in paths},
        "decision": "REJECT_CRYPTO_INTRADAY_COMPRESSION_NO_SQCLI",
        "reason": "Both topology-selected development representatives had negative stress expectancy and insufficient samples in independent 2025H1 validation.",
        "holdout_accessed": False, "sqcli_builder_executed": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--family", type=Path, required=True); parser.add_argument("--development", type=Path, required=True); parser.add_argument("--validation", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = build(args.family, args.development, args.validation); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n"); print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
