#!/usr/bin/env python3
"""Execute one uncensored SQ Retest and bind its orders export to one SQX."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Callable

from lab.sq_bridge.alquimia_retest import verify_retest_project
from lab.sq_bridge.sqcli_transport import (
    CONTAINER_NAME, SAFE_PROJECT_NAME, docker_exec_http_call,
    docker_project_final_log, gui_open_project, gui_start_project, list_projects,
)
from lab.sq_bridge.sqx_extract import extract as extract_sqx
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_retest_final_log(text: str) -> dict:
    """Prove one-input/one-output natural completion from SQ's own run log."""
    if not isinstance(text, str) or "TASK FINISHED" not in text:
        raise ValueError("RETEST_LOG_NOT_FINISHED")
    before = re.search(
        r"Databanks before start:\s*Results \((\d+)\),\s*PreHoldout \((\d+)\)", text)
    after = re.search(
        r"Databanks after finish:\s*Results \((\d+)\),\s*PreHoldout \((\d+)\)", text)
    totals = re.search(
        r"Total tested:\s*(\d+).*?Passed:\s*(\d+),\s*Failed:\s*(\d+)",
        text, re.DOTALL)
    if before is None or after is None or totals is None:
        raise ValueError("RETEST_LOG_COUNTERS_MISSING")
    values = tuple(map(int, (*before.groups(), *after.groups(), *totals.groups())))
    if values[:4] != (1, 0, 1, 1) or values[4] != 1 or values[5] + values[6] != 1:
        raise ValueError(f"RETEST_LOG_COUNTERS_INVALID: {values}")
    return {
        "input_before": values[0], "output_before": values[1],
        "input_after": values[2], "output_after": values[3],
        "total_tested": values[4], "passed": values[5], "failed": values[6],
    }


def _completed(path: Path, manifest: dict) -> dict:
    result = json.loads(path.read_text())
    if (result.get("decision") != "PASS_SUPERVISED_RETEST"
            or result.get("project_name") != manifest.get("project_name")
            or result.get("candidate_id") != manifest.get("candidate_id")):
        raise ValueError("completed Retest receipt identity mismatch")
    for prefix in ("manifest", "source_cfx", "candidate_input_sqx",
                   "imported_cfx", "retest_output_sqx", "orders_export_input_sqx",
                   "orders_csv",
                   "sq_final_log", "databank_sync_receipt",
                   "output_databank_sync_receipt"):
        source = Path(result.get(f"{prefix}_path", ""))
        if not source.is_file() or result.get(f"{prefix}_sha256") != _sha256(source):
            raise ValueError(f"completed Retest {prefix} path/hash mismatch")
    return verify_retest_receipt(
        path, candidate_id=manifest["candidate_id"],
        orders_path=Path(result["orders_csv_path"]))


def verify_retest_receipt(receipt_path: Path, *, candidate_id: str,
                          orders_path: Path) -> dict:
    """Rebuild the native lineage rather than trusting receipt booleans."""
    receipt_path, orders_path = receipt_path.resolve(), orders_path.resolve()
    result = json.loads(receipt_path.read_text())
    if (result.get("decision") != "PASS_SUPERVISED_RETEST"
            or result.get("candidate_id") != candidate_id
            or result.get("holdout_accessed") is not False
            or result.get("performance_filters_applied_in_sq") is not False
            or result.get("total_tested") != 1
            or result.get("input_before") != 1 or result.get("output_before") != 0
            or result.get("input_after") != 1 or result.get("output_after") != 1):
        raise ValueError("SUPERVISED_RETEST_RECEIPT_INVALID")
    files = {}
    for prefix in ("manifest", "source_cfx", "candidate_input_sqx",
                   "imported_cfx", "retest_output_sqx", "orders_export_input_sqx",
                   "orders_csv",
                   "sq_final_log", "databank_sync_receipt",
                   "output_databank_sync_receipt"):
        path = Path(result.get(f"{prefix}_path", "")).resolve()
        if not path.is_file() or result.get(f"{prefix}_sha256") != _sha256(path):
            raise ValueError(f"SUPERVISED_RETEST_{prefix.upper()}_INVALID")
        files[prefix] = path
    if files["orders_csv"] != orders_path:
        raise ValueError("SUPERVISED_RETEST_ORDERS_IDENTITY_MISMATCH")
    manifest = json.loads(files["manifest"].read_text())
    sync = json.loads(files["databank_sync_receipt"].read_text())
    output_sync = json.loads(files["output_databank_sync_receipt"].read_text())
    if (sync.get("decision") != "PASS_RETEST_DATABANK_SYNC"
            or sync.get("project_name") != result.get("project_name")
            or sync.get("databank") != "Results"
            or sync.get("observed_project_strategies") != 1
            or sync.get("input_copy_sha256")
                != result.get("candidate_input_sqx_sha256")):
        raise ValueError("SUPERVISED_RETEST_SYNC_RECEIPT_INVALID")
    if (output_sync.get("decision") != "PASS_RETEST_OUTPUT_DATABANK_SYNC"
            or output_sync.get("project_name") != result.get("project_name")
            or output_sync.get("databank") != "PreHoldout"
            or output_sync.get("observed_output_sqx_count") != 1
            or output_sync.get("output_sqx_sha256")
                != result.get("retest_output_sqx_sha256")):
        raise ValueError("SUPERVISED_RETEST_OUTPUT_SYNC_RECEIPT_INVALID")
    if (manifest.get("candidate_id") != candidate_id
            or manifest.get("project_name") != result.get("project_name")):
        raise ValueError("SUPERVISED_RETEST_MANIFEST_IDENTITY_MISMATCH")
    verify_retest_project(files["source_cfx"], manifest)
    verify_retest_project(files["imported_cfx"], manifest, require_archive_hash=False)
    input_contract = extract_sqx(files["candidate_input_sqx"])
    output_contract = extract_sqx(files["retest_output_sqx"])
    if (input_contract.get("strategy_name") != candidate_id
            or output_contract.get("strategy_name") != candidate_id
            or input_contract.get("strategy_xml_sha256")
                != output_contract.get("strategy_xml_sha256")
            or result.get("retest_output_strategy_xml_sha256")
                != output_contract.get("strategy_xml_sha256")):
        raise ValueError("SUPERVISED_RETEST_SQX_IDENTITY_MISMATCH")
    if _sha256(files["orders_export_input_sqx"]) != _sha256(files["retest_output_sqx"]):
        raise ValueError("SUPERVISED_RETEST_EXPORT_INPUT_MISMATCH")
    with zipfile.ZipFile(files["retest_output_sqx"]) as archive:
        if "orders.bin" not in archive.namelist() or not archive.read("orders.bin"):
            raise ValueError("SUPERVISED_RETEST_ORDERS_BIN_MISSING")
    counters = parse_retest_final_log(files["sq_final_log"].read_text())
    if any(result.get(key) != value for key, value in counters.items()):
        raise ValueError("SUPERVISED_RETEST_LOG_MISMATCH")
    return result


def supervised_retest(
    *, cfx_path: Path, manifest_path: Path, output_dir: Path,
    base_url: str = "http://127.0.0.1:8080", container: str = "sqcli-docker",
    projects_root: Path = Path("/mnt/volume-SQ/user/projects"),
    interval: int = 2, timeout_seconds: int = 1800,
    listing_fn: Callable[..., list[dict]] = list_projects,
    open_fn: Callable[..., dict] = gui_open_project,
    start_fn: Callable[..., dict] = gui_start_project,
    final_log_fn: Callable[..., dict] | None = None,
    sync_fn: Callable[[str], str] | None = None,
    export_fn: Callable[[str], str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleep_fn: Callable[[float], None] = time.sleep,
    project_verify_fn: Callable[..., dict] = verify_retest_project,
    completed_fn: Callable[[Path, dict], dict] | None = None,
    receipt_filename: str = "supervised_retest_receipt.json",
    receipt_decision: str = "PASS_SUPERVISED_RETEST",
) -> dict:
    if not CONTAINER_NAME.fullmatch(container):
        raise ValueError("invalid SQCLI container name")
    if (not isinstance(interval, int) or isinstance(interval, bool) or interval < 1
            or not isinstance(timeout_seconds, int) or timeout_seconds < interval):
        raise ValueError("invalid Retest monitoring interval/timeout")
    cfx_path, manifest_path = cfx_path.resolve(), manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text())
    if (not SAFE_PROJECT_NAME.fullmatch(receipt_filename.replace("_", "").replace(".", ""))
            or not SAFE_PROJECT_NAME.fullmatch(receipt_decision)):
        raise ValueError("invalid supervised Retest receipt identity")
    contract = project_verify_fn(cfx_path, manifest)
    project, candidate_id = contract["project_name"], contract["candidate_id"]
    if not SAFE_PROJECT_NAME.fullmatch(project):
        raise ValueError("invalid Retest project name")
    candidate = Path(manifest["candidate_sqx_path"]).resolve()
    output_dir = output_dir.resolve()
    project_dir = projects_root.resolve() / project
    final_receipt = output_dir / receipt_filename
    if final_receipt.is_file():
        return ((completed_fn or _completed)(final_receipt, manifest))
    preflight_path = output_dir / "retest_preflight.json"
    sync_path = output_dir / "retest_databank_sync_receipt.json"
    output_sync_path = output_dir / "retest_output_databank_sync_receipt.json"
    start_path = output_dir / "retest_start_receipt.json"
    preflight = {
        "schema_version": 1, "decision": "PASS_RETEST_PREFLIGHT",
        "project_name": project, "candidate_id": candidate_id,
        "manifest_path": str(manifest_path), "manifest_sha256": _sha256(manifest_path),
        "source_cfx_path": str(cfx_path), "source_cfx_sha256": _sha256(cfx_path),
        "candidate_input_sqx_path": str(candidate),
        "candidate_input_sqx_sha256": _sha256(candidate),
        "holdout_accessed": False, "sqcli_started": False,
        "paper_authorized": False, "live_authorized": False,
    }
    resuming = output_dir.exists() and any(output_dir.iterdir())
    if resuming:
        if not preflight_path.is_file() or json.loads(preflight_path.read_text()) != preflight:
            raise ValueError("incomplete Retest preflight mismatch")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_atomic(preflight_path, preflight)

    listing = listing_fn(base_url)
    running = sorted(row.get("projectName") for row in listing
                     if row.get("runningStatus") not in (None, 0)
                     and not (resuming and row.get("projectName") == project))
    current = [row for row in listing if row.get("projectName") == project]
    if running or (current and not resuming):
        raise RuntimeError(
            f"SQCLI Retest preflight collision running={running} project={bool(current)}")
    if not current:
        if start_path.is_file():
            raise RuntimeError("started Retest project disappeared")
        container_cfx = f"/tmp/alquimia-retest-{_sha256(cfx_path)[:16]}.cfx"
        copied = runner(
            ["docker", "cp", str(cfx_path), f"{container}:{container_cfx}"],
            capture_output=True, text=True, timeout=30, check=False)
        if copied.returncode != 0:
            raise RuntimeError("cannot stage Retest CFX")
        try:
            response = open_fn(base_url, container_cfx)
        finally:
            runner(["docker", "exec", container, "rm", "--", container_cfx],
                   capture_output=True, text=True, timeout=15, check=False)
        if response.get("projectName") != project:
            raise RuntimeError(f"SQCLI imported unexpected Retest project: {response}")
        current = [row for row in listing_fn(base_url)
                   if row.get("projectName") == project]
    if (len(current) != 1 or current[0].get("hasUnresolvedResources") is not False
            or (not start_path.is_file()
                and current[0].get("runningStatus") not in (None, 0))):
        raise RuntimeError("imported Retest project absent, running or unresolved")
    imported_cfx = project_dir / "project.cfx"
    project_verify_fn(imported_cfx, manifest, require_archive_hash=False)
    results_dir, retest_dir = project_dir / "databanks/Results", project_dir / "databanks/PreHoldout"
    results_dir.mkdir(parents=True, exist_ok=True)
    retest_dir.mkdir(parents=True, exist_ok=True)
    input_copy = results_dir / candidate.name
    if start_path.is_file():
        started = json.loads(start_path.read_text())
        if (started.get("decision") != "PASS_RETEST_STARTED"
                or started.get("project_name") != project
                or started.get("preflight_sha256") != _sha256(preflight_path)
                or started.get("databank_sync_receipt_path") != str(sync_path)
                or not sync_path.is_file()
                or started.get("databank_sync_receipt_sha256") != _sha256(sync_path)
                or started.get("input_copy_path") != str(input_copy)
                or not input_copy.is_file()
                or started.get("input_copy_sha256") != _sha256(input_copy)
                or _sha256(input_copy) != manifest["candidate_sqx_sha256"]):
            raise ValueError("incomplete Retest start receipt mismatch")
    else:
        existing_inputs = list(results_dir.glob("*.sqx"))
        if list(retest_dir.glob("*.sqx")):
            raise RuntimeError("unstarted Retest output databank is not clean")
        if not existing_inputs:
            shutil.copyfile(candidate, input_copy)
        elif existing_inputs != [input_copy] or _sha256(input_copy) != _sha256(candidate):
            raise RuntimeError("unstarted Retest input databank is not exact")
        if _sha256(input_copy) != manifest["candidate_sqx_sha256"]:
            raise RuntimeError("Retest input copy hash mismatch")
        sync_command = (
            f"-databank action=syncfromfiles project={project} name=Results")
        synchronizer = sync_fn or (
            lambda value: docker_exec_http_call(container, value))
        synced = [row for row in listing_fn(base_url)
                  if row.get("projectName") == project]
        if len(synced) == 1 and synced[0].get("strategies") == 1:
            # A previous process may have crashed after the asynchronous sync
            # became visible but before writing its receipt. Repeating SQ's
            # syncfromfiles duplicates the in-memory strategy, so recover it.
            sync_response = "recovered_already_synced_exact_databank"
        else:
            sync_response = synchronizer(sync_command)
            sync_deadline = time.monotonic() + min(60, timeout_seconds)
            while time.monotonic() < sync_deadline:
                synced = [row for row in listing_fn(base_url)
                          if row.get("projectName") == project]
                if len(synced) == 1 and synced[0].get("strategies") == 1:
                    break
                sleep_fn(min(interval, 5))
        if len(synced) != 1 or synced[0].get("strategies") != 1:
            raise RuntimeError("SQCLI did not load the exact Results SQX after sync")
        write_atomic(sync_path, {
            "schema_version": 1, "decision": "PASS_RETEST_DATABANK_SYNC",
            "project_name": project, "databank": "Results",
            "command": sync_command, "response": sync_response,
            "input_copy_path": str(input_copy),
            "input_copy_sha256": _sha256(input_copy),
            "observed_project_strategies": 1,
        })
        start = start_fn(base_url, project)
        if not isinstance(start, dict) or start.get("success") is None:
            raise RuntimeError(f"SQCLI Retest start failed: {start}")
        write_atomic(start_path, {
            "schema_version": 1, "decision": "PASS_RETEST_STARTED",
            "project_name": project, "preflight_path": str(preflight_path),
            "preflight_sha256": _sha256(preflight_path), "response": start,
            "databank_sync_receipt_path": str(sync_path),
            "databank_sync_receipt_sha256": _sha256(sync_path),
            "input_copy_path": str(input_copy),
            "input_copy_sha256": _sha256(input_copy),
        })

    finalizer = final_log_fn or (
        lambda project_name: docker_project_final_log(container, project_name))
    deadline = time.monotonic() + timeout_seconds
    observed_running = False
    final = None
    while time.monotonic() < deadline:
        rows = listing_fn(base_url)
        matches = [row for row in rows if row.get("projectName") == project]
        others = [row.get("projectName") for row in rows
                  if row.get("projectName") != project
                  and row.get("runningStatus") not in (None, 0)]
        if len(matches) != 1 or others:
            raise RuntimeError(f"Retest monitoring identity/concurrency failure: {others}")
        if matches[0].get("runningStatus") not in (None, 0):
            observed_running = True
        else:
            try:
                final = finalizer(project)
                break
            except RuntimeError:
                pass
        sleep_fn(interval)
    if final is None:
        raise TimeoutError("SQCLI Retest did not finish naturally within timeout")
    counters = parse_retest_final_log(final["log_text"])
    final_log_path = output_dir / "sq_retest_final.log"
    final_log_path.write_text(final["log_text"])

    outputs = list(retest_dir.glob("*.sqx"))
    output_sync_command = (
        f"-databank action=synctofiles project={project} name=PreHoldout")
    output_sync_response = "recovered_already_synced_exact_output"
    if not outputs:
        synchronizer = sync_fn or (
            lambda value: docker_exec_http_call(container, value))
        output_sync_response = synchronizer(output_sync_command)
    output_deadline = time.monotonic() + min(60, timeout_seconds)
    stable_signature = None
    output_ready = False
    while time.monotonic() < output_deadline:
        outputs = list(retest_dir.glob("*.sqx"))
        signature = None
        if len(outputs) == 1:
            try:
                with zipfile.ZipFile(outputs[0]) as archive:
                    if "orders.bin" in archive.namelist() and archive.read("orders.bin"):
                        signature = (outputs[0].stat().st_size, _sha256(outputs[0]))
            except (OSError, zipfile.BadZipFile):
                pass
        if signature is not None and signature == stable_signature:
            output_ready = True
            break
        stable_signature = signature
        sleep_fn(min(interval, 5))
    if len(outputs) != 1 or not output_ready:
        raise RuntimeError(f"Retest must produce exactly one SQX, got {len(outputs)}")
    retested = outputs[0].resolve()
    retested_contract = extract_sqx(retested)
    if retested_contract.get("strategy_name") != candidate_id:
        raise RuntimeError("Retest output candidate identity mismatch")
    with zipfile.ZipFile(retested) as archive:
        if "orders.bin" not in archive.namelist() or not archive.read("orders.bin"):
            raise RuntimeError("Retest output SQX has no non-empty orders.bin")
    write_atomic(output_sync_path, {
        "schema_version": 1, "decision": "PASS_RETEST_OUTPUT_DATABANK_SYNC",
        "project_name": project, "databank": "PreHoldout",
        "command": output_sync_command, "response": output_sync_response,
        "observed_output_sqx_count": 1,
        "output_sqx_path": str(retested), "output_sqx_sha256": _sha256(retested),
    })

    container_project = f"/home/squser/SQ/user/projects/{project}"
    export_token = _sha256(retested)[:16]
    export_input = project_dir / f"orders-export-input-{export_token}.sqx"
    if not export_input.exists():
        shutil.copyfile(retested, export_input)
    if _sha256(export_input) != _sha256(retested):
        raise RuntimeError("SQCLI orders export input copy hash mismatch")
    orders_prefix_name = f"orders-pre-holdout-{export_token}"
    orders_csv = (project_dir / f"{orders_prefix_name}.csv").resolve()
    command = (f"-tools action=orderstocsv file={container_project}/{export_input.name} "
               f"output={container_project}/{orders_prefix_name} "
               "usecomma=true data=main")
    exporter = export_fn or (lambda value: docker_exec_http_call(container, value))
    export_response = "reused_existing_verified_export"
    if not orders_csv.is_file():
        export_response = exporter(command)
    if not orders_csv.is_file() or orders_csv.stat().st_size == 0:
        raise RuntimeError("SQCLI orders export missing or empty")
    result = {
        "schema_version": 1, "decision": receipt_decision,
        "project_name": project, "candidate_id": candidate_id,
        "manifest_path": str(manifest_path), "manifest_sha256": _sha256(manifest_path),
        "source_cfx_path": str(cfx_path), "source_cfx_sha256": _sha256(cfx_path),
        "candidate_input_sqx_path": str(candidate),
        "candidate_input_sqx_sha256": _sha256(candidate),
        "imported_cfx_path": str(imported_cfx), "imported_cfx_sha256": _sha256(imported_cfx),
        "retest_output_sqx_path": str(retested), "retest_output_sqx_sha256": _sha256(retested),
        "retest_output_strategy_xml_sha256": retested_contract["strategy_xml_sha256"],
        "orders_export_input_sqx_path": str(export_input),
        "orders_export_input_sqx_sha256": _sha256(export_input),
        "orders_csv_path": str(orders_csv), "orders_csv_sha256": _sha256(orders_csv),
        "sq_final_log_path": str(final_log_path), "sq_final_log_sha256": _sha256(final_log_path),
        "preflight_path": str(preflight_path), "preflight_sha256": _sha256(preflight_path),
        "start_receipt_path": str(start_path), "start_receipt_sha256": _sha256(start_path),
        "databank_sync_receipt_path": str(sync_path),
        "databank_sync_receipt_sha256": _sha256(sync_path),
        "output_databank_sync_receipt_path": str(output_sync_path),
        "output_databank_sync_receipt_sha256": _sha256(output_sync_path),
        "completion_source": final.get("completion_source"),
        "observed_running": observed_running, **counters,
        "orders_export_command": command, "orders_export_response": export_response,
        "holdout_accessed": False, "performance_filters_applied_in_sq": False,
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(final_receipt, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cfx", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--container", default="sqcli-docker")
    parser.add_argument("--projects-root", type=Path,
                        default=Path("/mnt/volume-SQ/user/projects"))
    parser.add_argument("--interval", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    print(json.dumps(supervised_retest(
        cfx_path=args.cfx, manifest_path=args.manifest,
        output_dir=args.output_dir, base_url=args.base_url,
        container=args.container, projects_root=args.projects_root,
        interval=args.interval, timeout_seconds=args.timeout_seconds), indent=2))


if __name__ == "__main__":
    main()
