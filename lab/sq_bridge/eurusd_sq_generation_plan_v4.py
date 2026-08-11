#!/usr/bin/env python3
"""Compile a screened EURUSD hypothesis into an auditable SQ generation plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from lab.sq_bridge.eurusd_v4_hypotheses import (
    HYPOTHESIS_MARKET_SIDES as V4_HYPOTHESIS_MARKET_SIDES,
    SEARCH_PROFILES as V4_HYPOTHESIS_SEARCH_PROFILES,
    accepted_target,
)
from lab.sq_bridge.evidence_chain import verify as verify_chain
from lab.sq_bridge.temporal_split_contract_v4 import digest, sq_periods


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def compile_plan(*, screen_path: Path, chain_path: Path,
                 methodology_path: Path, period_contract_output: Path,
                 plan_output: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    chain = json.loads(chain_path.read_text())
    verification = verify_chain(chain, methodology_path)
    if (methodology.get("schema_version") != 4 or not verification.get("valid")
            or verification.get("terminal") or not verification.get("promotable")
            or verification.get("next_stage") != "sq_generation"):
        raise ValueError("evidence chain does not authorize SQ generation")
    receipts = chain.get("receipts") or []
    if len(receipts) != 2 or [row.get("stage") for row in receipts] != [
            "market_preflight", "hypothesis_screen"]:
        raise ValueError("SQ generation prerequisites are incomplete")
    receipt_screen = Path(receipts[1]["artifact"]).resolve()
    screen_path = screen_path.resolve()
    if (receipt_screen != screen_path
            or receipts[1].get("artifact_sha256") != sha256(screen_path)):
        raise ValueError("screen artifact is not the one frozen in the chain")
    screen = json.loads(screen_path.read_text())
    hypothesis_id = chain.get("hypothesis_id")
    if (screen.get("stage") != "hypothesis_screen" or screen.get("decision") != "PASS"
            or screen.get("campaign_id") != chain.get("campaign_id")
            or hypothesis_id not in screen.get("selected_hypothesis_ids", [])):
        raise ValueError("chain hypothesis did not pass the frozen screen")
    profile = V4_HYPOTHESIS_SEARCH_PROFILES.get(hypothesis_id)
    market_side = V4_HYPOTHESIS_MARKET_SIDES.get(hypothesis_id)
    if profile is None or market_side is None:
        raise ValueError("screened EURUSD hypothesis has no translatable SQ profile")
    trace_path = _resolve(
        screen_path.parent, screen.get("hypothesis_screen_trace_path", ""))
    if (not trace_path.is_file()
            or screen.get("hypothesis_screen_trace_sha256") != sha256(trace_path)):
        raise ValueError("screen trace hash mismatch")
    trace = json.loads(trace_path.read_text())
    contract = trace.get("temporal_contract")
    if (not isinstance(contract, dict)
            or trace.get("temporal_contract_sha256") != digest(contract)
            or contract.get("methodology_sha256") != sha256(methodology_path)):
        raise ValueError("screen temporal contract mismatch")
    period_contract_output.parent.mkdir(parents=True, exist_ok=True)
    period_contract_output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    safe_id = re.sub(r"[^A-Za-z0-9]+", "_", hypothesis_id).strip("_").upper()
    project_name = f"ALQUIMIA_EURUSD_D1_V4_{safe_id}"
    periods = sq_periods(contract)
    accepted_limit = accepted_target(
        hypothesis_id, screen["selected_hypothesis_ids"],
        methodology["sq_generation"]["accepted_candidates_global_budget"])
    plan = {
        "schema_version": 1, "decision": "PASS_GENERATION_PLAN",
        "campaign_id": chain["campaign_id"], "chain_hypothesis_id": hypothesis_id,
        "source_hypothesis_id": hypothesis_id, "market": "EURUSD",
        "project_name": project_name, "search_profile": profile,
        "generation_type": methodology["sq_generation"]["search_method"].replace("_", "-"),
        "attempt_budget": methodology["sq_generation"]["maximum_attempts"],
        "attempt_stop_guard": methodology["sq_generation"]["attempt_stop_guard"],
        "accepted_limit": accepted_limit, "market_side": market_side,
        "maximum_rules": methodology["sq_generation"]["max_rules"],
        "date_from": contract["source_first"], "date_to": contract["source_last"],
        "periods": periods, "holdout_sealed": True,
        "screen_artifact_path": str(screen_path),
        "screen_artifact_sha256": sha256(screen_path),
        "screen_trace_path": str(trace_path), "screen_trace_sha256": sha256(trace_path),
        "evidence_chain_path": str(chain_path.resolve()),
        "evidence_chain_sha256": sha256(chain_path),
        "temporal_split_contract_path": str(period_contract_output.resolve()),
        "temporal_split_contract_sha256": digest(contract),
        "alquimia_project_arguments": {
            "market": "EURUSD", "name": project_name,
            "search_profile": profile, "generation_type": "genetic-evolution",
            "attempt_budget": methodology["sq_generation"]["maximum_attempts"],
            "attempt_stop_guard": methodology["sq_generation"]["attempt_stop_guard"],
            "accepted_limit": accepted_limit, "market_side": market_side,
            "date_from": contract["source_first"], "date_to": contract["source_last"],
            "evidence_chain": str(chain_path.resolve()),
            "campaign_id": chain["campaign_id"],
            "source_hypothesis_id": hypothesis_id,
            "period_contract": str(period_contract_output.resolve()),
        },
        "performance_recomputed": False, "paper_authorized": False,
        "live_authorized": False,
    }
    plan_output.parent.mkdir(parents=True, exist_ok=True)
    plan_output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", type=Path, required=True)
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--period-contract-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compile_plan(
        screen_path=args.screen, chain_path=args.chain,
        methodology_path=args.methodology,
        period_contract_output=args.period_contract_output,
        plan_output=args.output)
    print(json.dumps({key: result[key] for key in (
        "decision", "source_hypothesis_id", "search_profile", "project_name",
        "attempt_budget")}, indent=2))


if __name__ == "__main__":
    main()
