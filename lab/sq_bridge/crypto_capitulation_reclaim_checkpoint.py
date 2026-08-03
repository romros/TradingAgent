#!/usr/bin/env python3
"""Verify terminal internal-research lineage for v19."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(family_path: Path, temporal_gate_path: Path, discovery_path: Path, walkforward_path: Path) -> dict:
    family, temporal, discovery, walkforward = map(load, (family_path, temporal_gate_path, discovery_path, walkforward_path))
    config_hash = canonical(family)
    if temporal["decision"] != "PASS_INTERNAL_NON_INDEPENDENT" or temporal["performance_promotion_authorized"]:
        raise ValueError("TEMPORAL_GATE_NOT_INTERNAL_ONLY")
    if discovery["config_sha256"] != config_hash or walkforward["config_sha256"] != config_hash:
        raise ValueError("CONFIG_LINEAGE_MISMATCH")
    if discovery["source_sha256"] != walkforward["source_sha256"]:
        raise ValueError("SOURCE_LINEAGE_MISMATCH")
    if not discovery["stable_candidate_ids"] or not discovery["topology_selected_representatives"]:
        raise ValueError("DISCOVERY_NOT_STABLE")
    if walkforward["decision"] != "REJECT_INTERNAL_WALK_FORWARD" or walkforward["passing_candidate_ids"]:
        raise ValueError("WALKFORWARD_NOT_TERMINAL_REJECTION")
    if walkforward["independent_validation"] or walkforward["global_holdout_accessed"] or walkforward["performance_promotion_authorized"]:
        raise ValueError("INDEPENDENCE_OR_HOLDOUT_CONTRACT_BROKEN")
    paths = (family_path, temporal_gate_path, discovery_path, walkforward_path)
    result = walkforward["results"][0]
    return {"schema_version": 1, "checkpoint_id": "crypto-capitulation-reclaim-v19-terminal",
        "source_sha256": discovery["source_sha256"], "points_evaluated": discovery["points_evaluated"],
        "development_passes": discovery["point_gate_passes"], "stable_candidate_ids": discovery["stable_candidate_ids"],
        "selected_candidate_ids": [row["candidate_id"] for row in discovery["topology_selected_representatives"]],
        "walkforward_stress_trades": result["aggregate_metrics"]["stress"]["trades"],
        "walkforward_stress_profit_factor": result["aggregate_metrics"]["stress"]["profit_factor"],
        "walkforward_positive_fold_ratio": result["positive_fold_ratio"],
        "failed_gates": ["minimum_total_trades", "minimum_trades_per_fold", "minimum_positive_fold_ratio"],
        "artifact_sha256": {str(path): sha(path) for path in paths},
        "decision": "REJECT_CRYPTO_CAPITULATION_RECLAIM_INTERNAL_WF",
        "independent_validation": False, "global_holdout_accessed": False, "sqcli_builder_executed": False,
        "performance_promotion_authorized": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--family", type=Path, required=True); parser.add_argument("--temporal-gate", type=Path, required=True); parser.add_argument("--discovery", type=Path, required=True); parser.add_argument("--walkforward", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = build(args.family, args.temporal_gate, args.discovery, args.walkforward); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n"); print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
