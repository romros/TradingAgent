#!/usr/bin/env python3
"""Verify terminal v15-v17 multi-crypto momentum research lineage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build(manifests: dict[str, Path], v15_path: Path, v16_path: Path, v17_path: Path,
          validation_path: Path, roundtrips: dict[str, Path] | None = None,
          receipts: tuple[Path, ...] = ()):
    source_hashes = {asset: load(path)["output_sha256"] for asset, path in manifests.items()}
    v15, v16, v17, validation = map(load, (v15_path, v16_path, v17_path, validation_path))
    if any(item["source_sha256"] != source_hashes for item in (v15, v16, v17)) or validation["source_sha256"] != source_hashes:
        raise ValueError("SOURCE_LINEAGE_MISMATCH")
    if v15["stable_candidate_ids"] or v16["stable_candidate_ids"]:
        raise ValueError("EARLY_FAMILY_NOT_TERMINAL")
    if validation["decision"] != "REJECT_TEMPORAL_VALIDATION" or validation["passing_candidate_ids"]:
        raise ValueError("V17_NOT_TERMINAL_REJECTION")
    if any(item.get("holdout_accessed") or item.get("oos_accessed") for item in (v15, v16, v17, validation)):
        raise ValueError("SEALED_PERIOD_ACCESSED")
    roundtrips = roundtrips or {}
    for asset, path in roundtrips.items():
        item = load(path)
        if item["source_sha256"] != source_hashes[asset]:
            raise ValueError(f"ROUNDTRIP_SOURCE_MISMATCH:{asset}")
        prices_exact = all(item["field_errors"][field]["changed_rows"] == 0 for field in ("open", "high", "low", "close"))
        if (item["decision"] != "PASS_SIGNAL_RESEARCH" or item["source_rows"] != 43200
                or item["exported_rows"] != 43200 or not item["timestamps_exact_and_ordered"]
                or not prices_exact or item["paper_or_live_authorized"]):
            raise ValueError(f"ROUNDTRIP_NOT_SIGNAL_SAFE:{asset}")
    paths = (*manifests.values(), v15_path, v16_path, v17_path, validation_path,
             *roundtrips.values(), *receipts)
    return {"schema_version": 1, "checkpoint_id": "crypto-momentum-v15-v17-terminal",
            "source_sha256": source_hashes,
            "v15": {"points": v15["points_evaluated"], "passes": v15["point_gate_passes"], "stable": len(v15["stable_candidate_ids"])},
            "v16": {"points": v16["points_evaluated"], "passes": v16["point_gate_passes"], "stable": len(v16["stable_candidate_ids"])},
            "v17": {"points": v17["points_evaluated"], "passes": v17["point_gate_passes"],
                    "stable": len(v17["stable_candidate_ids"]), "validation": validation["decision"]},
            "artifact_sha256": {str(path): sha(path) for path in paths},
            "sq_signal_sources": {asset: "PASS_SIGNAL_RESEARCH" for asset in roundtrips},
            "decision": "REJECT_CRYPTO_MOMENTUM_NO_OOS_NO_SQCLI",
            "reasons": ["V15 relative momentum had no development pass after 200-USDC risk scaling and oracle costs.",
                        "V16 dual momentum had two isolated passes but no stable region.",
                        "V17 local refinement formed a stable region but reversed to negative expectancy in independent validation."],
            "oos_accessed": False, "holdout_accessed": False, "sqcli_builder_executed": False,
            "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--btc-manifest", type=Path, required=True); parser.add_argument("--eth-manifest", type=Path, required=True); parser.add_argument("--sol-manifest", type=Path, required=True)
    parser.add_argument("--v15", type=Path, required=True); parser.add_argument("--v16", type=Path, required=True); parser.add_argument("--v17", type=Path, required=True); parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--eth-roundtrip", type=Path, required=True); parser.add_argument("--sol-roundtrip", type=Path, required=True)
    parser.add_argument("--sol-receipt", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = build({"BTCUSD": args.btc_manifest, "ETHUSD": args.eth_manifest, "SOLUSD": args.sol_manifest}, args.v15, args.v16, args.v17, args.validation,
                   {"ETHUSD": args.eth_roundtrip, "SOLUSD": args.sol_roundtrip}, (args.sol_receipt,))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n"); print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
