#!/usr/bin/env python3
"""Tradueix el subset SQX verificat a l'IR canònic i reproduïble d'Alquímia."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from lab.sq_bridge.sqx_extract import extract
except ModuleNotFoundError:
    from sqx_extract import extract


def canonical_ir(contract: dict) -> dict:
    if contract.get("translation_status") != "SUPPORTED_SUBSET":
        raise ValueError(
            f"SQX fora del subset traduible: {contract.get('unsupported_nodes_or_formulas')}")
    return {
        "schema_version": 1,
        "ir_type": "alquimia_strategy_ir",
        "translation_semantics": "exact_supported_subset",
        "strategy_id": contract["strategy_name"],
        "source_sqx_sha256": contract["source_sha256"],
        "source_strategy_xml_sha256": contract["strategy_xml_sha256"],
        "market": contract["market"],
        "execution": contract["execution"],
        "entries": contract["entries"],
        "entry_condition_counts": contract["entry_condition_counts"],
        "maximum_entry_conditions": contract["maximum_entry_conditions"],
        "exit_signals": contract["exit_signals"],
    }


def translate(sqx_path: Path, output_path: Path) -> dict:
    result = canonical_ir(extract(sqx_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqx", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = translate(args.sqx, args.output)
    print(json.dumps({"strategy_id": result["strategy_id"],
                      "maximum_entry_conditions": result["maximum_entry_conditions"]}, indent=2))


if __name__ == "__main__":
    main()
