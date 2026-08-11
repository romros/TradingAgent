#!/usr/bin/env python3
"""Compose a fail-closed, performance-blind crypto H4 research preflight."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _input(base: Path, value: str, label: str,
           reasons: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    path = _resolve(base, value)
    if not path.is_file():
        reasons.append(f"{label.upper()}_MISSING")
        return {}, {"path": str(path), "exists": False}
    try:
        result = _load(path)
    except (OSError, json.JSONDecodeError, ValueError):
        reasons.append(f"{label.upper()}_INVALID")
        result = {}
    return result, {"path": str(path), "exists": True,
                    "bytes": path.stat().st_size, "sha256": _sha(path)}


def _linked_file(value: Any, expected_sha: Any) -> bool:
    if not isinstance(value, str) or not isinstance(expected_sha, str):
        return False
    path = Path(value)
    return path.is_file() and _sha(path) == expected_sha


def compose(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _load(config_path)
    required = ("campaign_id", "market", "ostium_pair_id", "canonical_source",
                "sq_resource", "mapping", "costs", "preregistration")
    if config.get("schema_version") != 1 or any(not config.get(key) for key in required):
        raise ValueError("invalid crypto H4 preflight config")
    market = str(config["market"])
    if market not in ("BTCUSD", "ETHUSD"):
        raise ValueError("unsupported crypto H4 market")

    reasons: list[str] = []
    loaded: dict[str, dict[str, Any]] = {}
    inputs: dict[str, dict[str, Any]] = {}
    for label in ("canonical_source", "sq_resource", "mapping", "costs",
                  "preregistration"):
        loaded[label], inputs[label] = _input(
            config_path.parent, str(config[label]), label, reasons)
    canonical, resource, mapping, costs, prereg = (
        loaded[key] for key in ("canonical_source", "sq_resource", "mapping",
                                "costs", "preregistration"))

    if (canonical.get("decision") !=
            "PASS_CANONICAL_H4_PROXY_SOURCE_NOT_RESEARCH_AUTHORIZED"
            or canonical.get("research_symbol") != market
            or canonical.get("timeframe") != "H4"
            or canonical.get("performance_accessed") is not False
            or canonical.get("research_authorized") is not False
            or not _linked_file(canonical.get("canonical_path"),
                                canonical.get("canonical_sha256"))):
        reasons.append("CANONICAL_H4_SOURCE_NOT_PROVEN")

    canonical_ref = resource.get("canonical_receipt") or {}
    source_ref = resource.get("source") or {}
    commands_ref = resource.get("commands") or {}
    roundtrip = resource.get("roundtrip") or {}
    if (resource.get("decision") != "PASS_SQ_H4_PROXY_RESOURCE"
            or resource.get("campaign_id") != config["campaign_id"]
            or resource.get("timeframe") != "H4"
            or resource.get("performance_accessed") is not False
            or resource.get("research_authorized") is not False
            or canonical_ref.get("sha256") != inputs["canonical_source"].get("sha256")
            or source_ref.get("sha256") != canonical.get("canonical_sha256")
            or roundtrip.get("timestamps_exact_and_ordered") is not True
            or roundtrip.get("exact_ohlc_parity") is not True
            or not _linked_file(source_ref.get("path"), source_ref.get("sha256"))
            or not _linked_file(commands_ref.get("path"), commands_ref.get("sha256"))
            or not _linked_file(roundtrip.get("export_path"),
                                roundtrip.get("export_sha256"))):
        reasons.append("SQ_H4_RESOURCE_NOT_PROVEN")

    if (mapping.get("decision") != "PASS_CRYPTO_PROXY_MAPPING"
            or mapping.get("symbol") != market
            or mapping.get("performance_accessed") is not False
            or mapping.get("research_authorized") is not True
            or (mapping.get("canonical") or {}).get("sha256") !=
            inputs["canonical_source"].get("sha256")):
        reasons.append("CRYPTO_PROXY_MAPPING_NOT_MATURE")

    if (costs.get("decision") != "PASS_COSTS_FROZEN"
            or costs.get("costs_frozen") is not True
            or not (costs.get("by_notional") or {}).get("200")
            or costs.get("paper_authorized") is not False
            or costs.get("live_authorized") is not False):
        reasons.append("OSTIUM_200_USDC_COSTS_NOT_FROZEN")

    market_plan = (prereg.get("markets") or {}).get(market) or {}
    if (prereg.get("schema_version") != 1
            or prereg.get("performance_accessed") is not False
            or prereg.get("research_authorized") is not False
            or market_plan.get("campaign_id") != config["campaign_id"]
            or not market_plan.get("temporal_split_utc")):
        reasons.append("CRYPTO_CAMPAIGN_NOT_PREREGISTERED")

    reasons = sorted(set(reasons))
    passed = not reasons
    return {
        "schema_version": 1, "stage": "market_preflight",
        "campaign_id": config["campaign_id"], "market": market,
        "timeframe": "H4", "account_usdc": 200,
        "ostium_pair_id": str(config["ostium_pair_id"]),
        "decision": "PASS" if passed else "BLOCK",
        "market_executable": passed, "research_authorized": passed,
        "next_stage_authorized": "hypothesis_screen" if passed else None,
        "blocking_reasons": reasons,
        "mapping_progress": {
            "observations": mapping.get("observations", 0),
            "distinct_utc_dates": mapping.get("distinct_utc_dates", 0),
            "observed_span_days": mapping.get("observed_span_days", 0),
            "upstream_blocking_reasons": mapping.get("blocking_reasons", []),
        },
        "cost_progress": {
            "decision": costs.get("decision"),
            "coverage": costs.get("coverage"),
            "remaining_complete_captures_lower_bound":
                costs.get("remaining_complete_captures_lower_bound"),
        },
        "input_receipts": inputs,
        "campaign_config_path": str(config_path),
        "campaign_config_sha256": _sha(config_path),
        "candidate_ids": [], "performance_accessed": False,
        "holdout_accessed": False, "future_periods_sealed": True,
        "sqcli_authorized": False, "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compose(args.config)
    write_atomic(args.output.resolve(), result)
    print(json.dumps({"decision": result["decision"],
                      "market": result["market"],
                      "blocking_reasons": result["blocking_reasons"],
                      "mapping_progress": result["mapping_progress"],
                      "cost_progress": result["cost_progress"]}, indent=2))


if __name__ == "__main__":
    main()
