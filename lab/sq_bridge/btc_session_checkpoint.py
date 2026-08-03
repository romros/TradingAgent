#!/usr/bin/env python3
"""Verify terminal BTC v13/v14 session-family falsification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path): return json.loads(path.read_text())
def sha(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build(manifest_path: Path, breakout_path: Path, fade_path: Path) -> dict:
    manifest, breakout, fade = load(manifest_path), load(breakout_path), load(fade_path)
    if not (manifest["output_sha256"] == breakout["source_sha256"] == fade["source_sha256"]):
        raise ValueError("SOURCE_LINEAGE_MISMATCH")
    if breakout["stable_candidate_ids"] or fade["stable_candidate_ids"]:
        raise ValueError("SESSION_FAMILY_NOT_TERMINAL")
    if breakout["validation_accessed"] or fade["validation_accessed"] or breakout["holdout_accessed"] or fade["holdout_accessed"]:
        raise ValueError("SEALED_PERIOD_ACCESSED")
    return {"schema_version": 1, "checkpoint_id": "btc-session-v13-v14-terminal",
            "source_sha256": manifest["output_sha256"],
            "v13_breakout": {"points": breakout["points_evaluated"], "point_passes": breakout["point_gate_passes"],
                              "stable_candidates": len(breakout["stable_candidate_ids"])},
            "v14_fade": {"points": fade["points_evaluated"], "point_passes": fade["point_gate_passes"],
                          "stable_candidates": len(fade["stable_candidate_ids"])},
            "artifact_sha256": {str(path): sha(path) for path in (manifest_path, breakout_path, fade_path)},
            "decision": "REJECT_BTC_SESSION_FAMILIES_NO_VALIDATION_NO_SQCLI",
            "reasons": ["V13 continuation produced zero development passes.",
                        "V14 fade produced one isolated point pass but no stable parameter region."],
            "validation_accessed": False, "oos_accessed": False, "holdout_accessed": False,
            "sqcli_executed": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--breakout", type=Path, required=True); parser.add_argument("--fade", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = build(args.manifest, args.breakout, args.fade); args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n"); print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
