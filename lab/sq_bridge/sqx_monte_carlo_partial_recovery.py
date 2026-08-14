#!/usr/bin/env python3
"""Recover incomplete native SQ parameter-MC orders without calling them a pass."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.sqx_monte_carlo_materialize import COMMON_MEMBERS, _write_sqx


RESULT_SUFFIX = "/MonteCarloRetest_Results.xml"
ORDER_RE = re.compile(
    r"^(?P<prefix>Results/.+)/MonteCarloRetest_Simulation(?P<index>\d+)Orders\.bin$"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_partial(path: Path, *, requested_simulations: int,
                    probability_pct: int, max_change_pct: int) -> dict:
    """Inspect only the narrow SQ failure observed: a trailing missing batch."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        results = [name for name in names if name.endswith(RESULT_SUFFIX)]
        if len(results) != 1:
            raise ValueError("PARTIAL_MC_RESULT_XML_NOT_UNIQUE")
        result_name = results[0]
        root = ET.fromstring(archive.read(result_name))
        declared = int(root.findtext("./NumberOfSimulations", "0"))
        prefix = result_name[:-len(RESULT_SUFFIX)]
        rows = []
        for name in names:
            match = ORDER_RE.match(name)
            if match and match.group("prefix") == prefix:
                payload = archive.read(name)
                rows.append((int(match.group("index")), name, len(payload),
                             hashlib.sha256(payload).hexdigest()))
    method = [value.strip() for value in root.itertext() if value.strip().startswith(
        "Randomize strategy parameters")]
    expected_method = ("Randomize strategy parameters, with probability "
                       f"{probability_pct} % and max change {max_change_pct} %")
    ordered = sorted(rows)
    indices = [row[0] for row in ordered]
    persisted = len(ordered)
    missing = list(range(persisted, requested_simulations))
    if (declared != requested_simulations or method != [expected_method]
            or persisted >= requested_simulations
            or indices != list(range(persisted))
            or not missing or len(missing) > 64
            or any(size <= 0 for _, _, size, _ in ordered)):
        raise ValueError("PARTIAL_MC_NOT_A_SAFE_TRAILING_BATCH_FAILURE")
    return {
        "schema_version": 1,
        "evidence_type": "strategyquant_native_parameter_mc_incomplete",
        "decision": "INCOMPLETE_NOT_CANONICAL_PASS",
        "sqx_path": str(path.resolve()),
        "sqx_sha256": _sha(path),
        "requested_simulations": requested_simulations,
        "declared_simulations": declared,
        "persisted_simulations": persisted,
        "missing_simulation_indices": missing,
        "missing_runs_must_count_as_failures": True,
        "probability_pct": probability_pct,
        "max_change_pct": max_change_pct,
        "simulation_order_members": [row[1] for row in ordered],
        "simulation_order_sha256": [row[3] for row in ordered],
        "canonical_robustness_authorized": False,
        "holdout_accessed": False,
    }


def materialize_partial(source: Path, output_dir: Path, **expectation: int) -> dict:
    contract = inspect_partial(source, **expectation)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = output_dir / "partial-materialization.manifest.json"
    if any(output_dir.iterdir()):
        raise ValueError("PARTIAL_MC_MATERIALIZATION_DIRECTORY_NOT_EMPTY")
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        required = set(COMMON_MEMBERS) - {"META-INF/MANIFEST.MF"}
        if required - names:
            raise ValueError("PARTIAL_MC_COMMON_MEMBERS_MISSING")
        common = {name: archive.read(name) for name in COMMON_MEMBERS if name in names}
        runs = []
        for index, member in enumerate(contract["simulation_order_members"]):
            payload = archive.read(member)
            target = output_dir / f"simulation-{index:04d}.sqx"
            _write_sqx(target, {**common, "orders.bin": payload})
            runs.append({
                "run_id": f"run-{index:04d}",
                "source_orders_member": member,
                "source_orders_sha256": hashlib.sha256(payload).hexdigest(),
                "materialized_sqx_path": str(target.resolve()),
                "materialized_sqx_sha256": _sha(target),
            })
    result = {
        "schema_version": 1,
        "artifact_type": "strategyquant_partial_mc_order_materialization",
        "decision": "RECOVERED_FOR_DIAGNOSTIC_ONLY",
        "source_sqx_path": str(source.resolve()),
        "source_sqx_sha256": _sha(source),
        "partial_native_contract": contract,
        "runs": runs,
        "canonical_robustness_authorized": False,
        "holdout_accessed": False,
    }
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def verify_partial_manifest(path: Path) -> dict:
    result = json.loads(path.read_text())
    if (result.get("artifact_type")
            != "strategyquant_partial_mc_order_materialization"
            or result.get("decision") != "RECOVERED_FOR_DIAGNOSTIC_ONLY"
            or result.get("canonical_robustness_authorized") is not False
            or result.get("holdout_accessed") is not False):
        raise ValueError("PARTIAL_MC_MATERIALIZATION_INVALID")
    source = Path(result.get("source_sqx_path", ""))
    contract = result.get("partial_native_contract") or {}
    if not source.is_file() or result.get("source_sqx_sha256") != _sha(source):
        raise ValueError("PARTIAL_MC_MATERIALIZATION_SOURCE_INVALID")
    rebuilt = inspect_partial(
        source,
        requested_simulations=contract.get("requested_simulations"),
        probability_pct=contract.get("probability_pct"),
        max_change_pct=contract.get("max_change_pct"),
    )
    if rebuilt != contract:
        raise ValueError("PARTIAL_MC_MATERIALIZATION_CONTRACT_INVALID")
    runs = result.get("runs")
    if not isinstance(runs, list) or len(runs) != contract["persisted_simulations"]:
        raise ValueError("PARTIAL_MC_MATERIALIZATION_RUNS_INVALID")
    with zipfile.ZipFile(source) as archive:
        for index, row in enumerate(runs):
            member = contract["simulation_order_members"][index]
            payload = archive.read(member)
            target = Path(row.get("materialized_sqx_path", ""))
            if (row.get("run_id") != f"run-{index:04d}"
                    or row.get("source_orders_member") != member
                    or row.get("source_orders_sha256")
                       != hashlib.sha256(payload).hexdigest()
                    or not target.is_file()
                    or row.get("materialized_sqx_sha256") != _sha(target)):
                raise ValueError("PARTIAL_MC_MATERIALIZATION_LINEAGE_INVALID")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqx", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--requested-simulations", required=True, type=int)
    parser.add_argument("--probability-pct", required=True, type=int)
    parser.add_argument("--max-change-pct", required=True, type=int)
    args = parser.parse_args()
    result = materialize_partial(
        args.sqx, args.output_dir,
        requested_simulations=args.requested_simulations,
        probability_pct=args.probability_pct,
        max_change_pct=args.max_change_pct,
    )
    print(json.dumps({"decision": result["decision"],
                      "runs": len(result["runs"])}, indent=2))


if __name__ == "__main__":
    main()
