#!/usr/bin/env python3
"""Build a deterministic acquisition/parity plan for the Ostium research universe."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def action_for(market: dict) -> str:
    if market["local_history"] == "ready" and market["parity"] != "pass":
        return "REFRESH_PARITY"
    if market["dukascopy"] == "verified_available" and market["local_history"] == "missing":
        return "BACKFILL_THEN_PARITY"
    if market["dukascopy"] in {"verify", "proxy_mapping_required"}:
        return "VERIFY_SOURCE_AND_MAPPING"
    return "BLOCK_REVIEW_CONTRACT"


def build_plan(catalog: dict) -> dict:
    rows = []
    for market in catalog["markets"]:
        row = dict(market)
        row["next_action"] = action_for(market)
        row["research_authorized"] = (
            market["local_history"] == "ready" and market["parity"] == "pass"
        )
        rows.append(row)
    rows.sort(key=lambda row: (row["priority"], row["class"], row["symbol"]))
    return {
        "schema_version": 1,
        "catalog_as_of": catalog["as_of"],
        "research_authorized": [r["symbol"] for r in rows if r["research_authorized"]],
        "queue": rows,
        "policy": "Performance remains sealed until research_authorized=true."
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = build_plan(json.loads(args.catalog.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"authorized": plan["research_authorized"],
                      "first": [(r["symbol"], r["next_action"]) for r in plan["queue"][:8]]}, indent=2))


if __name__ == "__main__":
    main()
