#!/usr/bin/env python3
"""Validate a complete SQ Signal probe log and emit canonical entry signals."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

try:
    from lab.sq_bridge.python_parity_trace_v4 import load_mt4_csv
    from lab.sq_bridge.sqx_extract import extract
except ModuleNotFoundError:
    from python_parity_trace_v4 import load_mt4_csv
    from sqx_extract import extract


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(raw: str, unit: str) -> pd.Timestamp:
    try:
        value = int(raw)
        result = pd.Timestamp(value, unit=unit, tz="UTC")
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"SQ strategy time invalid: {raw!r}") from error
    if result.year < 1990 or result.year > 2100:
        raise ValueError(f"SQ strategy time fora de rang: {raw!r}")
    return result


def _gate_value(gate: dict, values: dict[str, bool]) -> bool:
    op = gate.get("op")
    if op == "var":
        if gate.get("id") not in values:
            raise ValueError("Variable absent en avaluar el gate SQ")
        return values[gate["id"]]
    children = gate.get("children", [])
    if op == "and" and children:
        return all(_gate_value(child, values) for child in children)
    if op == "not" and len(children) == 1:
        return not _gate_value(children[0], values)
    raise ValueError(f"Gate SQ invalid: {op}")


def convert(*, raw_log_path: Path, sqx_path: Path, market_data_path: Path,
            build_receipt_path: Path, time_unit: str, signals_path: Path,
            scoped_market_path: Path, receipt_path: Path) -> dict:
    if time_unit not in {"s", "ms"}:
        raise ValueError("time_unit ha de ser s o ms")
    contract = extract(sqx_path)
    if not contract["supported"]:
        raise ValueError("SQX fora del subset Alquimia suportat")
    build_receipt = json.loads(build_receipt_path.read_text())
    if (build_receipt.get("decision") != "PASS_SIGNAL_PROBE_JAR"
            or build_receipt.get("production_sq_modified") is not False
            or build_receipt.get("log_schema")
            != "sq_strategy_time_long;signal_variable_uuid;boolean_0_or_1"):
        raise ValueError("Receipt del probe no valid")
    jar_path = Path(build_receipt.get("output_jar_path", ""))
    if (not jar_path.is_file()
            or _sha(jar_path) != build_receipt.get("output_jar_sha256")):
        raise ValueError("JAR del probe absent o diferent del receipt")

    expected = set(contract["signal_variable_ids"])
    active = {
        direction: entry["entry_gate"]
        for direction, entry in contract["entries"].items() if entry is not None
    }
    used = {value for entry in contract["entries"].values() if entry is not None
            for value in entry["signal_variable_ids_used"]}
    if not active or not used.issubset(expected):
        raise ValueError("Mapping de variables d'entrada incomplet")
    by_time: dict[pd.Timestamp, dict[str, bool]] = defaultdict(dict)
    row_count = 0
    with raw_log_path.open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.reader(handle, delimiter=";"), 1):
            if len(row) != 3:
                raise ValueError(f"Fila probe {line_number} no te 3 camps")
            timestamp = _timestamp(row[0], time_unit)
            variable = row[1].strip()
            if variable not in expected:
                raise ValueError(f"Variable SQ desconeguda: {variable!r}")
            if row[2] not in {"0", "1"}:
                raise ValueError(f"Boolea SQ invalid a fila {line_number}")
            if variable in by_time[timestamp]:
                raise ValueError("Variable SQ duplicada dins la mateixa barra")
            by_time[timestamp][variable] = row[2] == "1"
            row_count += 1
    if not by_time:
        raise ValueError("Log del probe buit")
    incomplete = [timestamp for timestamp, values in by_time.items()
                  if set(values) != expected]
    if incomplete:
        raise ValueError(f"Barres amb cobertura de variables incompleta: {len(incomplete)}")
    ordered_times = sorted(by_time)
    if list(by_time) != ordered_times:
        raise ValueError("Log del probe desordenat temporalment")

    market = load_mt4_csv(market_data_path)
    market_times = set(market.index)
    outside = [timestamp for timestamp in ordered_times if timestamp not in market_times]
    if outside:
        raise ValueError(f"Barres del probe fora de les candles congelades: {len(outside)}")
    source_lines = market_data_path.read_text(encoding="utf-8-sig").splitlines()
    scoped_lines = []
    scoped_times = []
    for line_number, line in enumerate(source_lines, 1):
        fields = line.split(",")
        if len(fields) != 7:
            raise ValueError(f"Candle font invalida a fila {line_number}")
        try:
            timestamp = pd.Timestamp(
                f"{fields[0]} {fields[1]}", tz="UTC")
        except ValueError as error:
            raise ValueError(f"Timestamp candle invalid a fila {line_number}") from error
        if timestamp in by_time:
            scoped_lines.append(line)
            scoped_times.append(timestamp)
    if scoped_times != ordered_times:
        raise ValueError("Les candles restringides no coincideixen exactament amb el probe")
    scoped_market_path.parent.mkdir(parents=True, exist_ok=True)
    scoped_market_path.write_text("\n".join(scoped_lines) + "\n")
    signal_rows = [
        (timestamp.isoformat().replace("+00:00", "Z"), direction)
        for timestamp in ordered_times
        for direction in sorted(active)
        if _gate_value(active[direction], by_time[timestamp])
    ]
    if signal_rows != sorted(set(signal_rows)):
        raise ValueError("Senyals d'entrada duplicats o desordenats")
    signals_path.parent.mkdir(parents=True, exist_ok=True)
    with signals_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\n")
        writer.writerow(("Timestamp", "Direction"))
        writer.writerows(signal_rows)
    result = {
        "schema_version": 1,
        "decision": "PASS_COMPLETE_SQ_SIGNAL_LOG",
        "raw_log_path": str(raw_log_path.resolve()),
        "raw_log_sha256": _sha(raw_log_path),
        "probe_jar_sha256": build_receipt["output_jar_sha256"],
        "probe_build_receipt_sha256": _sha(build_receipt_path),
        "sqx_path": str(sqx_path.resolve()),
        "sqx_sha256": contract["source_sha256"],
        "market_data_path": str(market_data_path.resolve()),
        "market_data_sha256": _sha(market_data_path),
        "scoped_market_data_path": str(scoped_market_path.resolve()),
        "scoped_market_data_sha256": _sha(scoped_market_path),
        "scoped_market_rows": len(scoped_lines),
        "time_unit": time_unit,
        "expected_variable_ids": sorted(expected),
        "active_entry_gates": dict(sorted(active.items())),
        "logged_bars": len(ordered_times),
        "raw_rows": row_count,
        "complete_rows_expected": len(ordered_times) * len(expected),
        "true_entry_signals": len(signal_rows),
        "first_logged_bar": ordered_times[0].isoformat().replace("+00:00", "Z"),
        "last_logged_bar": ordered_times[-1].isoformat().replace("+00:00", "Z"),
        "signals_path": str(signals_path.resolve()),
        "signals_sha256": _sha(signals_path),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-log", required=True, type=Path)
    parser.add_argument("--sqx", required=True, type=Path)
    parser.add_argument("--market-data", required=True, type=Path)
    parser.add_argument("--build-receipt", required=True, type=Path)
    parser.add_argument("--time-unit", required=True, choices=("s", "ms"))
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--scoped-market-data", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = convert(raw_log_path=args.raw_log, sqx_path=args.sqx,
                     market_data_path=args.market_data,
                     build_receipt_path=args.build_receipt,
                     time_unit=args.time_unit, signals_path=args.signals,
                     scoped_market_path=args.scoped_market_data,
                     receipt_path=args.receipt)
    print(json.dumps({key: result[key] for key in
                      ("decision", "logged_bars", "true_entry_signals")}, indent=2))


if __name__ == "__main__":
    main()
