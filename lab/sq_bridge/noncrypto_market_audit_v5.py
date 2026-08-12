#!/usr/bin/env python3
"""Fail-closed, performance-blind audit of the non-crypto Ostium universe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = Path(__file__).with_name("noncrypto_market_audit_spec_v5.json")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(relative: str, root: Path) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"evidence escapes repository: {relative}") from exc
    if not candidate.is_file():
        raise ValueError(f"evidence missing: {relative}")
    return candidate


def _assert_blind(document: dict[str, Any], label: str) -> None:
    forbidden_true = ("performance_accessed", "holdout_accessed", "paper_authorized", "live_authorized")
    for field in forbidden_true:
        if document.get(field) is True:
            raise ValueError(f"{label}: forbidden {field}=true")
    candidates = document.get("candidate_ids", [])
    if candidates not in (None, []):
        raise ValueError(f"{label}: quantitative candidates are not admissible")


def _technical_gate(gate: dict[str, Any], root: Path) -> dict[str, Any]:
    path_text = str(gate["path"])
    path = _resolve(path_text, root)
    evidence = _read_json(path)
    _assert_blind(evidence, path_text)
    reasons: list[str] = []
    allowlist = gate.get("decision_allowlist")
    if allowlist is not None and evidence.get("decision") not in allowlist:
        reasons.append(f"DECISION_NOT_ALLOWED:{evidence.get('decision')}")
    for field, expected in gate.get("required_fields", {}).items():
        if evidence.get(field) != expected:
            reasons.append(f"FIELD_MISMATCH:{field}")
    return {
        "role": gate["role"],
        "path": path_text,
        "sha256": _sha256(path),
        "decision": evidence.get("decision"),
        "pass": not reasons,
        "reasons": reasons,
    }


def _cost_gate(path_text: str, root: Path) -> dict[str, Any]:
    path = _resolve(path_text, root)
    evidence = _read_json(path)
    _assert_blind(evidence, path_text)
    frozen = evidence.get("costs_frozen") is True
    return {
        "path": path_text,
        "sha256": _sha256(path),
        "decision": evidence.get("decision"),
        "costs_frozen": frozen,
        "coverage": evidence.get("coverage"),
        "qualifying_complete_days": evidence.get("qualifying_complete_days"),
        "paper_pass": frozen,
    }


def audit(spec_path: Path = DEFAULT_SPEC, *, root: Path = ROOT) -> dict[str, Any]:
    spec = _read_json(spec_path)
    _assert_blind(spec, str(spec_path))
    if spec.get("legacy_candidates_reused") is not False:
        raise ValueError("spec must explicitly reject legacy candidate reuse")
    allowed = set(spec.get("allowed_categories", []))
    if "crypto" in allowed:
        raise ValueError("crypto category is forbidden")

    seen: set[str] = set()
    markets: list[dict[str, Any]] = []
    for market in spec.get("markets", []):
        symbol = str(market["symbol"]).upper()
        category = str(market["category"]).lower()
        if symbol in seen:
            raise ValueError(f"duplicate market: {symbol}")
        seen.add(symbol)
        if category == "crypto" or category not in allowed:
            raise ValueError(f"forbidden category for {symbol}: {category}")
        technical = [_technical_gate(item, root) for item in market["technical_evidence"]]
        known_blockers = list(market.get("known_research_blockers", []))
        technical_pass = bool(technical) and all(item["pass"] for item in technical) and not known_blockers
        costs = _cost_gate(str(market["cost_evidence"]), root)
        markets.append({
            "symbol": symbol,
            "category": category,
            "ostium_pair": market["ostium_pair"],
            "timeframe": market["timeframe"],
            "technical_evidence": technical,
            "known_research_blockers": known_blockers,
            "cost_evidence": costs,
            "research_decision": "PASS_RESEARCH_DATA_READY" if technical_pass else "BLOCK_TECHNICAL_EVIDENCE",
            "paper_decision": (
                "PASS_PAPER_INPUTS_READY" if technical_pass and costs["paper_pass"]
                else "BLOCK_PAPER_INPUTS"
            ),
        })

    research_ready = sum(item["research_decision"].startswith("PASS") for item in markets)
    paper_ready = sum(item["paper_decision"].startswith("PASS") for item in markets)
    return {
        "schema_version": 1,
        "audit_id": spec["audit_id"],
        "spec_path": str(spec_path.relative_to(root) if spec_path.is_relative_to(root) else spec_path),
        "spec_sha256": _sha256(spec_path),
        "performance_accessed": False,
        "holdout_accessed": False,
        "legacy_candidates_reused": False,
        "market_count": len(markets),
        "research_ready_count": research_ready,
        "paper_ready_count": paper_ready,
        "markets": markets,
        "decision": (
            "PASS_RESEARCH_UNIVERSE_WITH_PAPER_BLOCKS"
            if markets and research_ready == len(markets) and paper_ready < len(markets)
            else "PASS_RESEARCH_AND_PAPER_UNIVERSE"
            if markets and paper_ready == len(markets)
            else "PARTIAL_RESEARCH_UNIVERSE_WITH_PAPER_BLOCKS"
            if research_ready > 0
            else "BLOCK_NONCRYPTO_UNIVERSE"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.spec.resolve())
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
