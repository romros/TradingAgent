#!/usr/bin/env python3
"""Build a deterministic SQ task scaffold for quarantined SPY benchmark data."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source: Path, output: Path) -> dict:
    with zipfile.ZipFile(source) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    task_name = next(name for name in members if name.endswith("Task1.xml"))
    task = ET.fromstring(members[task_name])
    symbols = task.find("./Resources/Symbols")
    template = next(iter(symbols)) if symbols is not None and len(symbols) else None
    if symbols is None or template is None:
        raise ValueError("SOURCE_SYMBOL_RESOURCE_MISSING")
    symbol = copy.deepcopy(template)
    symbol.attrib.update({
        "name": "SPY_benchmark.D", "uSymbol": "SPY_benchmark",
        "uSymbolName": "SPY_benchmark", "precision": "D1",
        "timezone": "America/New_York", "removeWeekends": "true",
    })
    info = symbol.find("InstrumentInfo")
    if info is None:
        raise ValueError("SOURCE_INSTRUMENT_INFO_MISSING")
    info.attrib.update({
        "instrument": "SPY_benchmark", "description": "History data instrument",
        "decimals": "2", "tickSize": "0.01", "tickStep": "0.01",
        "pointValue": "1.0", "orderSizeMultiplier": "1.0",
        "orderSizeStep": "1.0", "defaultSpread": "0.0",
        "defaultSlippage": "0.0",
    })
    symbols.clear()
    symbols.append(symbol)
    members[task_name] = ET.tostring(task, encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            archive.writestr(name, members[name])
    result = {
        "schema_version": 1, "decision": "PASS_SPY_RESOURCE_SCAFFOLD",
        "source_path": str(source.resolve()), "source_sha256": sha256(source),
        "output_path": str(output.resolve()), "output_sha256": sha256(output),
        "symbol": "SPY_benchmark.D", "timeframe": "D1",
        "source_classification": "SQ_PROPRIETARY_QUARANTINE",
        "external_export_permitted": False, "ibkr_contract_verified": False,
    }
    output.with_suffix(".receipt.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
