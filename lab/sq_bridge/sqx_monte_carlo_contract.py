#!/usr/bin/env python3
"""Verify native StrategyQuant parameter-randomization evidence inside one SQX."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


RESULT_SUFFIX = "/MonteCarloRetest_Results.xml"
ORDER_RE = re.compile(r"^(?P<prefix>Results/.+)/MonteCarloRetest_Simulation(?P<index>\d+)Orders\.bin$")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path: Path, *, simulations: int, probability_pct: int,
            max_change_pct: int) -> dict:
    if simulations < 1 or not 1 <= probability_pct <= 100 \
            or not 1 <= max_change_pct <= 100:
        raise ValueError("SQX_MONTE_CARLO_EXPECTATION_INVALID")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        result_names = [name for name in names if name.endswith(RESULT_SUFFIX)]
        if len(result_names) != 1:
            raise ValueError("SQX_MONTE_CARLO_RESULT_XML_NOT_UNIQUE")
        result_name = result_names[0]
        root = ET.fromstring(archive.read(result_name))
        prefix = result_name[:-len(RESULT_SUFFIX)]
        order_rows = []
        for name in names:
            match = ORDER_RE.match(name)
            if match and match.group("prefix") == prefix:
                info = archive.getinfo(name)
                order_rows.append((int(match.group("index")), name, info.file_size,
                                   hashlib.sha256(archive.read(name)).hexdigest()))
    try:
        observed = int(root.findtext("./NumberOfSimulations", ""))
    except ValueError as exc:
        raise ValueError("SQX_MONTE_CARLO_RESULT_COUNT_INVALID") from exc
    methods = [text.strip() for text in root.itertext() if text.strip()
               and text.strip().startswith("Randomize strategy parameters")]
    symbol = (root.findtext("./Symbol") or "").strip()
    timeframe = (root.findtext("./TimeFrame") or "").strip()
    date_range = (root.findtext("./DateRange") or "").strip()
    expected_method = ("Randomize strategy parameters, with probability "
                       f"{probability_pct} % and max change {max_change_pct} %")
    indices = [row[0] for row in sorted(order_rows)]
    if (observed != simulations or methods != [expected_method]
            or not symbol or not timeframe
            or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2} - \d{4}\.\d{2}\.\d{2}",
                                date_range)
            or indices != list(range(simulations))
            or any(size <= 0 for _, _, size, _ in order_rows)):
        raise ValueError("SQX_MONTE_CARLO_NATIVE_EVIDENCE_INVALID")
    ordered = sorted(order_rows)
    return {
        "schema_version": 1,
        "evidence_type": "strategyquant_native_parameter_monte_carlo",
        "sqx_path": str(path.resolve()),
        "sqx_sha256": _sha(path),
        "result_xml_member": result_name,
        "method": "RandomizeStrategyParameters",
        "simulations": observed,
        "probability_pct": probability_pct,
        "max_change_pct": max_change_pct,
        "symbol": symbol,
        "timeframe": timeframe,
        "date_range": date_range,
        "simulation_order_members": [name for _, name, _, _ in ordered],
        "simulation_order_sha256": [digest for _, _, _, digest in ordered],
        "all_simulation_orders_nonempty": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqx", required=True, type=Path)
    parser.add_argument("--simulations", required=True, type=int)
    parser.add_argument("--probability-pct", required=True, type=int)
    parser.add_argument("--max-change-pct", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect(args.sqx, simulations=args.simulations,
                     probability_pct=args.probability_pct,
                     max_change_pct=args.max_change_pct)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
