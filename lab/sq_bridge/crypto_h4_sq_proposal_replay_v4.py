#!/usr/bin/env python3
"""Replay a normalized SQ proposal on sealed train data before any cost/OOS access."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from lab.sq_bridge.crypto_h4_train_engine_v4 import load_train, metrics, simulate


def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def gross_gate(summary: dict) -> tuple[str, list[str]]:
    reasons = []
    if summary["closed_trades"] < 50: reasons.append("MINIMUM_50_CLOSED_TRADES")
    pf = summary["profit_factor"]
    if not isinstance(pf, (int, float)) or pf < 1.2: reasons.append("GROSS_PROFIT_FACTOR_BELOW_1_2")
    if summary["net_pnl_usdc"] <= 0: reasons.append("GROSS_NET_PNL_NOT_POSITIVE")
    if summary["positive_calendar_years_ratio"] < .6:
        reasons.append("GROSS_POSITIVE_YEAR_RATIO_BELOW_0_6")
    return ("REJECT_SQ_PROPOSAL_CANONICAL_GROSS" if reasons
            else "PASS_GROSS_REQUIRES_FROZEN_COST_GATE", reasons)


def replay(*, normalized_path: Path, source_receipt_path: Path,
           preregistration_path: Path) -> dict:
    normalized_path, source_receipt_path, preregistration_path = (
        path.resolve() for path in
        (normalized_path, source_receipt_path, preregistration_path))
    proposal = json.loads(normalized_path.read_text())
    source_receipt = json.loads(source_receipt_path.read_text())
    prereg = json.loads(preregistration_path.read_text())
    if (proposal.get("decision") != "PASS_NORMALIZED_SQ_PROPOSAL_NOT_CANDIDATE"
            or proposal.get("performance_accessed") is not False
            or proposal.get("strategy_promotion_authorized") is not False):
        raise ValueError("normalized SQ proposal contract invalid")
    market = proposal["market"]
    source = Path(source_receipt["canonical_path"]).resolve()
    if (source_receipt.get("canonical_sha256") != _sha(source)
            or source_receipt.get("research_symbol") != market):
        raise ValueError("canonical source binding changed")
    split = prereg["markets"][market]["temporal_split_utc"]
    train_from = datetime.strptime(split["train"][0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    train_to = datetime.strptime(split["train"][1], "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc)
    bars = load_train(source, train_from, train_to)
    trades = simulate(bars, proposal["mechanism"], proposal["direction"],
                      proposal["normalized_parameters"])
    zero = {"by_notional": {"200": {f"{scenario}_roundtrip_bps": 0
                                      for scenario in ("base", "conservative", "stress")}},
            "carry": {side: {f"{scenario}_annual_cost_pct": 0
                              for scenario in ("base", "conservative", "stress")}
                      for side in ("long", "short")}}
    summary = metrics(trades, zero, "base")
    decision, reasons = gross_gate(summary)
    return {"schema_version": 1, "decision": decision, "rejection_reasons": reasons,
            "normalized_proposal_path": str(normalized_path),
            "normalized_proposal_sha256": _sha(normalized_path),
            "canonical_source_path": str(source), "canonical_source_sha256": _sha(source),
            "train_period_utc": [split["train"][0], split["train"][1]],
            "parameters": proposal["normalized_parameters"], "gross_train_metrics": summary,
            "costs_accessed": False, "validation_accessed": False,
            "oos_accessed": False, "holdout_accessed": False,
            "strategy_promotion_authorized": False,
            "remaining_gate": (None if reasons else "FROZEN_OSTIUM_COSTS_AND_NEIGHBORHOOD")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized", required=True, type=Path)
    parser.add_argument("--source-receipt", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = replay(normalized_path=args.normalized,
                    source_receipt_path=args.source_receipt,
                    preregistration_path=args.preregistration)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__": main()
