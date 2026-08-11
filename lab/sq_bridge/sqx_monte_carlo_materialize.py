#!/usr/bin/env python3
"""Materialize native MC order members as deterministic SQX files for orderstocsv."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from lab.sq_bridge.sqx_monte_carlo_contract import inspect
from lab.sq_bridge.sqcli_supervised_monte_carlo import verify_monte_carlo_receipt


COMMON_MEMBERS = ("META-INF/MANIFEST.MF", "settings.xml",
                  "strategy_Portfolio.xml", "version.txt")


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write_sqx(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, members[name])


def materialize(source: Path, output_dir: Path, *, simulations: int,
                probability_pct: int, max_change_pct: int,
                supervised_mc_receipt: Path | None = None) -> dict:
    contract = inspect(source, simulations=simulations,
                       probability_pct=probability_pct,
                       max_change_pct=max_change_pct)
    output_dir.mkdir(parents=True, exist_ok=True)
    unexpected = [path for path in output_dir.iterdir()
                  if path.name != "materialization.manifest.json"]
    if unexpected:
        raise ValueError("MONTE_CARLO_MATERIALIZATION_DIRECTORY_NOT_EMPTY")
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        required = set(COMMON_MEMBERS) - {"META-INF/MANIFEST.MF"}
        if required - names:
            raise ValueError("MONTE_CARLO_SQX_COMMON_MEMBERS_MISSING")
        common = {name: archive.read(name) for name in COMMON_MEMBERS if name in names}
        rows = []
        for index, member in enumerate(contract["simulation_order_members"]):
            orders = archive.read(member)
            target = output_dir / f"simulation-{index:04d}.sqx"
            _write_sqx(target, {**common, "orders.bin": orders})
            rows.append({
                "run_id": f"run-{index:04d}",
                "source_orders_member": member,
                "source_orders_sha256": _sha_bytes(orders),
                "materialized_sqx_path": str(target.resolve()),
                "materialized_sqx_sha256": _sha(target),
            })
    result = {
        "schema_version": 1,
        "artifact_type": "strategyquant_native_mc_order_materialization",
        "source_sqx_path": str(source.resolve()),
        "source_sqx_sha256": _sha(source),
        "native_contract": contract,
        "runs": rows,
    }
    if supervised_mc_receipt is None:
        result["evidence_class"] = "synthetic_control"
    else:
        supervised_mc_receipt = supervised_mc_receipt.resolve()
        receipt = verify_monte_carlo_receipt(supervised_mc_receipt)
        if (Path(receipt["retest_output_sqx_path"]).resolve() != source.resolve()
                or receipt["retest_output_sqx_sha256"] != _sha(source)):
            raise ValueError("MONTE_CARLO_MATERIALIZATION_RECEIPT_SOURCE_MISMATCH")
        result.update({
            "evidence_class": "observed",
            "supervised_mc_receipt_path": str(supervised_mc_receipt),
            "supervised_mc_receipt_sha256": _sha(supervised_mc_receipt),
        })
    manifest = output_dir / "materialization.manifest.json"
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def verify_manifest(path: Path) -> dict:
    result = json.loads(path.read_text())
    source = Path(result.get("source_sqx_path", ""))
    if not source.is_file() or result.get("source_sqx_sha256") != _sha(source):
        raise ValueError("MONTE_CARLO_MATERIALIZATION_SOURCE_INVALID")
    evidence_class = result.get("evidence_class")
    if evidence_class == "observed":
        receipt_path = Path(result.get("supervised_mc_receipt_path", ""))
        if (not receipt_path.is_file()
                or result.get("supervised_mc_receipt_sha256") != _sha(receipt_path)):
            raise ValueError("MONTE_CARLO_MATERIALIZATION_RECEIPT_INVALID")
        receipt = verify_monte_carlo_receipt(receipt_path)
        if (Path(receipt["retest_output_sqx_path"]).resolve() != source.resolve()
                or receipt["retest_output_sqx_sha256"] != _sha(source)):
            raise ValueError("MONTE_CARLO_MATERIALIZATION_RECEIPT_SOURCE_MISMATCH")
    elif evidence_class != "synthetic_control":
        raise ValueError("MONTE_CARLO_MATERIALIZATION_EVIDENCE_CLASS_INVALID")
    native = result.get("native_contract") or {}
    rebuilt = inspect(source, simulations=native.get("simulations"),
                      probability_pct=native.get("probability_pct"),
                      max_change_pct=native.get("max_change_pct"))
    if rebuilt != native:
        raise ValueError("MONTE_CARLO_MATERIALIZATION_CONTRACT_INVALID")
    rows = result.get("runs")
    if not isinstance(rows, list) or len(rows) != native["simulations"]:
        raise ValueError("MONTE_CARLO_MATERIALIZATION_RUNS_INVALID")
    with zipfile.ZipFile(source) as archive:
        for index, row in enumerate(rows):
            target = Path(row.get("materialized_sqx_path", ""))
            member = native["simulation_order_members"][index]
            orders = archive.read(member)
            if (row.get("run_id") != f"run-{index:04d}"
                    or row.get("source_orders_member") != member
                    or row.get("source_orders_sha256") != _sha_bytes(orders)
                    or not target.is_file()
                    or row.get("materialized_sqx_sha256") != _sha(target)):
                raise ValueError("MONTE_CARLO_MATERIALIZATION_LINEAGE_INVALID")
            with zipfile.ZipFile(target) as generated:
                if generated.read("orders.bin") != orders:
                    raise ValueError("MONTE_CARLO_MATERIALIZATION_ORDERS_INVALID")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqx", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--simulations", required=True, type=int)
    parser.add_argument("--probability-pct", required=True, type=int)
    parser.add_argument("--max-change-pct", required=True, type=int)
    parser.add_argument("--supervised-mc-receipt", required=True, type=Path)
    args = parser.parse_args()
    result = materialize(args.sqx, args.output_dir,
                         simulations=args.simulations,
                         probability_pct=args.probability_pct,
                         max_change_pct=args.max_change_pct,
                         supervised_mc_receipt=args.supervised_mc_receipt)
    print(json.dumps({"runs": len(result["runs"]),
                      "source_sqx_sha256": result["source_sqx_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
