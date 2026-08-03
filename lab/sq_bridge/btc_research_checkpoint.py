#!/usr/bin/env python3
"""Verify and summarize the terminal BTC v11/v12 proxy-research checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def build(manifest_path: Path, v11_train_path: Path, v11_validation_path: Path,
          v12_development_path: Path, v12_validation_path: Path) -> dict:
    manifest, train, validation = load(manifest_path), load(v11_train_path), load(v11_validation_path)
    development, regime_validation = load(v12_development_path), load(v12_validation_path)
    if manifest["output_sha256"] != train["source_sha256"] or train["source_sha256"] != development["source_sha256"]:
        raise ValueError("SOURCE_LINEAGE_MISMATCH")
    if validation["decision"] != "REJECT_TEMPORAL_VALIDATION" or regime_validation["decision"] != "REJECT_TEMPORAL_VALIDATION":
        raise ValueError("CHECKPOINT_IS_NOT_TERMINAL_REJECTION")
    if any(item.get("holdout_accessed") for item in (train, validation, development, regime_validation)):
        raise ValueError("HOLDOUT_WAS_ACCESSED")
    return {
        "schema_version": 1,
        "checkpoint_id": "btc-proxy-research-v11-v12-terminal",
        "source": {"rows": manifest["rows"], "first_utc": manifest["first_utc"], "last_utc": manifest["last_utc"],
                   "sha256": manifest["output_sha256"], "continuity": manifest["continuity"]},
        "v11": {"points": train["points_evaluated"], "point_passes": train["point_gate_passes"],
                "representatives": len(train["topology_selected_representatives"]), "validation_decision": validation["decision"],
                "validation_passes": validation["passing_candidate_ids"]},
        "v12": {"points": development["points_evaluated"], "point_passes": development["point_gate_passes"],
                "representatives": len(development["topology_selected_representatives"]), "validation_decision": regime_validation["decision"],
                "validation_passes": regime_validation["passing_candidate_ids"]},
        "artifact_sha256": {str(path): digest(path) for path in (manifest_path, v11_train_path, v11_validation_path,
                                                                 v12_development_path, v12_validation_path)},
        "decision": "REJECT_BTC_PROXY_FAMILIES_NO_SQCLI",
        "reasons": ["V11 long compression and pullback regions reversed to negative expectancy in 2022-2023.",
                    "V12 regime-filtered short breakout produced only three validation trades in 2023-2024 and all lost.",
                    "Native Ostium BTCUSD maturity/parity is still unavailable."],
        "oos_accessed": False, "holdout_accessed": False, "sqcli_executed": False,
        "paper_or_live_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True); parser.add_argument("--v11-train", type=Path, required=True)
    parser.add_argument("--v11-validation", type=Path, required=True); parser.add_argument("--v12-development", type=Path, required=True)
    parser.add_argument("--v12-validation", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); result = build(args.manifest, args.v11_train, args.v11_validation, args.v12_development, args.v12_validation)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "oos_accessed": False, "holdout_accessed": False, "sqcli_executed": False}, indent=2))


if __name__ == "__main__": main()
