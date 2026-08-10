#!/usr/bin/env python3
"""Bootstrap verified EURUSD v4 hypothesis branches up to SQ generation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.evidence_chain import append_receipt, new_chain, verify
from lab.sq_bridge.eurusd_d1_hypothesis_trace_v4 import build as build_trace
from lab.sq_bridge.eurusd_sq_generation_plan_v4 import compile_plan
from lab.sq_bridge.hypothesis_screen_artifact_v4 import build_artifact as build_screen
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bootstrap(*, preflight_path: Path, source_path: Path, cost_model_path: Path,
              methodology_path: Path, output_dir: Path) -> dict:
    paths = [preflight_path, source_path, cost_model_path, methodology_path]
    if any(not path.resolve().is_file() for path in paths):
        raise ValueError("bootstrap input missing")
    preflight_path, source_path, cost_model_path, methodology_path = (
        path.resolve() for path in paths)
    preflight = json.loads(preflight_path.read_text())
    methodology = json.loads(methodology_path.read_text())
    campaign_id = preflight.get("campaign_id")
    cost_receipt = ((preflight.get("input_receipts") or {}).get("costs") or {})
    if (preflight.get("stage") != "market_preflight"
            or preflight.get("decision") != "PASS"
            or preflight.get("next_stage_authorized") != "hypothesis_screen"
            or not isinstance(campaign_id, str)
            or cost_receipt.get("sha256") != sha256(cost_model_path)):
        raise ValueError("verified preflight does not authorize this cost model")
    receipt = {"decision": "PASS", "candidate_ids": [],
               "holdout_accessed": False, "artifact": str(preflight_path)}
    errors = validate_stage_artifact(
        "market_preflight", preflight, receipt, methodology,
        campaign_id, "alquimia_native")
    if errors:
        raise ValueError(f"market preflight contract invalid: {errors}")

    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / "eurusd_d1_hypothesis_screen.trace.json"
    write_atomic(trace_path, build_trace(source_path, cost_model_path, methodology_path))
    screen_path = output_dir / "eurusd_d1_hypothesis_screen.artifact.json"
    screen = build_screen(
        campaign_id=campaign_id, trace_path=trace_path,
        cost_model_path=cost_model_path, methodology_path=methodology_path,
        artifact_path=screen_path)
    selected = screen["selected_hypothesis_ids"]
    branches = {}
    for hypothesis_id in selected:
        branch = output_dir / hypothesis_id
        branch.mkdir(exist_ok=True)
        chain = new_chain(methodology_path, campaign_id, hypothesis_id,
                          "EURUSD", "alquimia_native")
        chain = append_receipt(
            chain, methodology, "market_preflight", preflight_path, "PASS", [])
        chain = append_receipt(
            chain, methodology, "hypothesis_screen", screen_path, "PASS", [])
        chain_path = branch / "chain.json"
        write_atomic(chain_path, chain)
        verification = verify(chain, methodology_path)
        if (not verification["valid"] or not verification["promotable"]
                or verification["next_stage"] != "sq_generation"):
            raise ValueError(f"branch {hypothesis_id} is not authorized: "
                             f"{verification['errors']}")
        contract_path = branch / "temporal_split_contract.json"
        plan_path = branch / "sq_generation_plan.json"
        plan = compile_plan(
            screen_path=screen_path, chain_path=chain_path,
            methodology_path=methodology_path,
            period_contract_output=contract_path, plan_output=plan_path)
        branches[hypothesis_id] = {
            "chain_path": str(chain_path.resolve()),
            "chain_sha256": sha256(chain_path),
            "generation_plan_path": str(plan_path.resolve()),
            "generation_plan_sha256": sha256(plan_path),
            "search_profile": plan["search_profile"],
        }
    result = {
        "schema_version": 1,
        "decision": "PASS_SQ_BRANCHES_READY" if branches else "REJECT_NO_HYPOTHESIS",
        "campaign_id": campaign_id,
        "source_sha256": sha256(source_path),
        "cost_model_sha256": sha256(cost_model_path),
        "preflight_sha256": sha256(preflight_path),
        "trace_path": str(trace_path.resolve()), "trace_sha256": sha256(trace_path),
        "screen_path": str(screen_path.resolve()), "screen_sha256": sha256(screen_path),
        "selected_hypothesis_ids": selected, "branches": branches,
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(output_dir / "bootstrap.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = bootstrap(
        preflight_path=args.preflight, source_path=args.source,
        cost_model_path=args.cost_model, methodology_path=args.methodology,
        output_dir=args.output_dir)
    print(json.dumps({key: result[key] for key in (
        "decision", "selected_hypothesis_ids", "sqcli_started")}, indent=2))


if __name__ == "__main__":
    main()
