#!/usr/bin/env python3
"""Run one candidate's native SQ parameter Monte Carlo under durable supervision."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from lab.sq_bridge.alquimia_monte_carlo import verify_project
from lab.sq_bridge.sqcli_supervised_retest import (
    parse_retest_final_log, supervised_retest,
)
from lab.sq_bridge.sqx_extract import extract as extract_sqx
from lab.sq_bridge.sqx_monte_carlo_contract import inspect


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_monte_carlo_receipt(path: Path, manifest: dict | None = None) -> dict:
    result = json.loads(path.read_text())
    if (result.get("decision") != "PASS_SUPERVISED_MONTE_CARLO"
            or result.get("holdout_accessed") is not False
            or result.get("performance_filters_applied_in_sq") is not False
            or result.get("total_tested") != 1
            or result.get("input_before") != 1 or result.get("output_before") != 0
            or result.get("input_after") != 1 or result.get("output_after") != 1):
        raise ValueError("SUPERVISED_MONTE_CARLO_RECEIPT_INVALID")
    files = {}
    for prefix in ("manifest", "source_cfx", "candidate_input_sqx",
                   "imported_cfx", "retest_output_sqx", "orders_export_input_sqx",
                   "orders_csv", "sq_final_log", "databank_sync_receipt",
                   "output_databank_sync_receipt"):
        source = Path(result.get(f"{prefix}_path", ""))
        if not source.is_file() or result.get(f"{prefix}_sha256") != _sha(source):
            raise ValueError(f"SUPERVISED_MONTE_CARLO_{prefix.upper()}_INVALID")
        files[prefix] = source
    observed_manifest = json.loads(files["manifest"].read_text())
    if manifest is not None and manifest != observed_manifest:
        raise ValueError("SUPERVISED_MONTE_CARLO_MANIFEST_MISMATCH")
    manifest = observed_manifest
    source_contract = verify_project(files["source_cfx"], manifest)
    imported_contract = verify_project(
        files["imported_cfx"], manifest, require_archive_hash=False)
    if source_contract != imported_contract:
        raise ValueError("SUPERVISED_MONTE_CARLO_IMPORTED_PROJECT_MISMATCH")
    input_contract = extract_sqx(files["candidate_input_sqx"])
    output_contract = extract_sqx(files["retest_output_sqx"])
    if (result.get("candidate_id") != manifest.get("candidate_id")
            or input_contract.get("strategy_name") != manifest.get("candidate_id")
            or output_contract.get("strategy_name") != manifest.get("candidate_id")
            or input_contract.get("strategy_xml_sha256")
                != output_contract.get("strategy_xml_sha256")
            or result.get("retest_output_strategy_xml_sha256")
                != output_contract.get("strategy_xml_sha256")
            or _sha(files["orders_export_input_sqx"])
                != _sha(files["retest_output_sqx"])):
        raise ValueError("SUPERVISED_MONTE_CARLO_CANDIDATE_MISMATCH")
    native = inspect(
        files["retest_output_sqx"], simulations=manifest["simulations"],
        probability_pct=manifest["probability_pct"],
        max_change_pct=manifest["max_change_pct"])
    counters = parse_retest_final_log(files["sq_final_log"].read_text())
    if any(result.get(key) != value for key, value in counters.items()):
        raise ValueError("SUPERVISED_MONTE_CARLO_LOG_MISMATCH")
    sync = json.loads(files["databank_sync_receipt"].read_text())
    output_sync = json.loads(files["output_databank_sync_receipt"].read_text())
    if (sync.get("observed_project_strategies") != 1
            or sync.get("input_copy_sha256")
                != result.get("candidate_input_sqx_sha256")
            or output_sync.get("observed_output_sqx_count") != 1
            or output_sync.get("output_sqx_sha256")
                != result.get("retest_output_sqx_sha256")):
        raise ValueError("SUPERVISED_MONTE_CARLO_DATABANK_SYNC_INVALID")
    with zipfile.ZipFile(files["retest_output_sqx"]) as archive:
        if "orders.bin" not in archive.namelist() or not archive.read("orders.bin"):
            raise ValueError("SUPERVISED_MONTE_CARLO_MAIN_ORDERS_INVALID")
    if native["simulations"] != manifest["simulations"]:
        raise ValueError("SUPERVISED_MONTE_CARLO_NATIVE_COUNT_INVALID")
    return result


def supervised_monte_carlo(*, cfx_path: Path, manifest_path: Path,
                           output_dir: Path, **kwargs) -> dict:
    result = supervised_retest(
        cfx_path=cfx_path, manifest_path=manifest_path,
        output_dir=output_dir, project_verify_fn=verify_project,
        completed_fn=verify_monte_carlo_receipt,
        receipt_filename="supervised_monte_carlo_receipt.json",
        receipt_decision="PASS_SUPERVISED_MONTE_CARLO", **kwargs)
    return verify_monte_carlo_receipt(
        output_dir.resolve() / "supervised_monte_carlo_receipt.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cfx", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--container", default="sqcli-docker")
    parser.add_argument("--projects-root", type=Path,
                        default=Path("/mnt/volume-SQ/user/projects"))
    parser.add_argument("--interval", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    args = parser.parse_args()
    result = supervised_monte_carlo(
        cfx_path=args.cfx, manifest_path=args.manifest,
        output_dir=args.output_dir, base_url=args.base_url,
        container=args.container, projects_root=args.projects_root,
        interval=args.interval, timeout_seconds=args.timeout_seconds)
    print(json.dumps({"decision": result["decision"],
                      "candidate_id": result["candidate_id"],
                      "total_tested": result["total_tested"]}, indent=2))


if __name__ == "__main__":
    main()
