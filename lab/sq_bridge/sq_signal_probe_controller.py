#!/usr/bin/env python3
"""Safely switch between normal SQCLI and an isolated signal-probe process."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from lab.sq_bridge.sq_signal_probe_build import SUPPORTED_SIGNAL_SOURCE_SHA256
from lab.sq_bridge.sqcli_supervised_retest import (
    inspect_signal_probe_runtime, supervised_retest, verify_retest_receipt,
)
from lab.sq_bridge.sqcli_transport import CONTAINER_NAME, list_projects_with_status
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


NORMAL_INTERNAL = "/home/squser/SQ/internal"
NORMAL_USER = "/home/squser/SQ/user"
MACHINE_ID = "/etc/machine-id"
PROBE_JAR = f"{NORMAL_INTERNAL}/libs/Snippets.jar"
PROBE_LOG_ROOT = "/probe"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _completed(runner: Callable[..., subprocess.CompletedProcess], args: list[str],
               *, timeout: int = 30) -> subprocess.CompletedProcess:
    result = runner(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {args[:3]}: {result.stderr[-1000:]}")
    return result


def _inspect(runner: Callable[..., subprocess.CompletedProcess], name: str) -> dict | None:
    result = runner(["docker", "inspect", name], capture_output=True, text=True,
                    timeout=30, check=False)
    if result.returncode != 0:
        diagnostic = f"{result.stdout}\n{result.stderr}"
        diagnostic_lower = diagnostic.lower()
        if "no such object" in diagnostic_lower or "no such container" in diagnostic_lower:
            return None
        raise RuntimeError(f"cannot inspect Docker container {name}: {diagnostic[-500:]}")
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("invalid docker inspect response") from error
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("docker inspect did not return one container")
    return rows[0]


def _mount(info: dict, destination: str) -> dict:
    rows = [row for row in info.get("Mounts", [])
            if isinstance(row, dict) and row.get("Destination") == destination]
    if len(rows) != 1 or rows[0].get("Type") != "bind":
        raise ValueError(f"normal SQCLI mount absent or ambiguous: {destination}")
    return rows[0]


def _validate_build_receipt(path: Path) -> tuple[dict, Path]:
    path = path.resolve()
    value = json.loads(path.read_text())
    jar = Path(value.get("output_jar_path", "")).resolve()
    if (value.get("decision") != "PASS_SIGNAL_PROBE_JAR"
            or value.get("production_sq_modified") is not False
            or value.get("source_sha256") not in SUPPORTED_SIGNAL_SOURCE_SHA256
            or value.get("java_class_major_version") != 66
            or not jar.is_file() or value.get("output_jar_sha256") != _sha(jar)):
        raise ValueError("signal probe build receipt is not executable")
    return value, jar


def _safe_output(output_dir: Path, raw_log_path: Path) -> tuple[Path, str]:
    output_dir, raw_log_path = output_dir.resolve(), raw_log_path.resolve()
    try:
        relative = raw_log_path.relative_to(output_dir)
    except ValueError as error:
        raise ValueError("raw signal log must be inside the dedicated output directory") from error
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("raw signal log relative path is unsafe")
    return output_dir, f"{PROBE_LOG_ROOT}/{relative.as_posix()}"


def build_run_command(*, normal: dict, probe_name: str, jar: Path,
                      output_dir: Path, container_log_path: str) -> list[str]:
    if not CONTAINER_NAME.fullmatch(probe_name) or probe_name == normal.get("Name", "").lstrip("/"):
        raise ValueError("invalid or colliding signal probe container name")
    config, host = normal.get("Config", {}), normal.get("HostConfig", {})
    image = normal.get("Image")
    user = config.get("User")
    if not isinstance(image, str) or not image.startswith("sha256:") or not user:
        raise ValueError("normal SQCLI image/user contract unavailable")
    user_mount = _mount(normal, NORMAL_USER)
    internal_mount = _mount(normal, NORMAL_INTERNAL)
    machine_mount = _mount(normal, MACHINE_ID)
    if (user_mount.get("RW") is not True or internal_mount.get("RW") is not True
            or machine_mount.get("RW") is not False):
        raise ValueError("normal SQCLI mount permissions differ from the safe contract")
    resource_options: list[str] = []
    memory = host.get("Memory", 0)
    memory_swap = host.get("MemorySwap", 0)
    nano_cpus = host.get("NanoCpus", 0)
    if isinstance(memory, int) and memory > 0:
        resource_options.extend(["--memory", str(memory)])
    if isinstance(memory_swap, int) and memory_swap >= memory > 0:
        resource_options.extend(["--memory-swap", str(memory_swap)])
    if isinstance(nano_cpus, int) and nano_cpus > 0:
        cpus = nano_cpus / 1_000_000_000
        if not math.isfinite(cpus) or cpus <= 0:
            raise ValueError("invalid normal SQCLI CPU limit")
        resource_options.extend(["--cpus", f"{cpus:g}"])
    command = [
        "docker", "run", "-d", "--name", probe_name, *resource_options,
        "--user", str(user), "--publish", "127.0.0.1:8080:8080",
        "--env", f"ALQUIMIA_SIGNAL_LOG_PATH={container_log_path}",
        "--mount", f"type=bind,src={user_mount['Source']},dst={NORMAL_USER}",
        "--mount", f"type=bind,src={internal_mount['Source']},dst={NORMAL_INTERNAL},readonly",
        "--tmpfs", f"{NORMAL_INTERNAL}/tmp:rw,mode=1777",
        "--tmpfs", f"{NORMAL_INTERNAL}/testfiles:rw,mode=1777",
        "--mount", f"type=bind,src={jar.resolve()},dst={PROBE_JAR},readonly",
        "--mount", f"type=bind,src={output_dir.resolve()},dst={PROBE_LOG_ROOT}",
        "--mount", f"type=bind,src={machine_mount['Source']},dst={MACHINE_ID},readonly",
        "--entrypoint", "/home/squser/SQ/sqcli",
    ]
    return [*command, image, "-gui"]


def _wait_healthy(base_url: str, *, list_fn: Callable[..., list[dict]],
                  sleep_fn: Callable[[float], None], attempts: int = 30) -> list[dict]:
    last_error = None
    for _ in range(attempts):
        try:
            return list_fn(base_url)
        except Exception as error:  # Java/HTTP transition boundary
            last_error = error
            sleep_fn(2)
    raise RuntimeError(f"SQCLI API did not become healthy: {last_error}")


def _running_projects(rows: list[dict]) -> list[str]:
    return sorted(str(row.get("projectName")) for row in rows
                  if row.get("runningStatus") not in {None, 0})


def start(*, journal_path: Path, build_receipt_path: Path, output_dir: Path,
          raw_log_path: Path, normal_name: str = "sqcli-docker",
          probe_name: str = "sqcli-signal-probe",
          base_url: str = "http://127.0.0.1:8080",
          runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
          list_fn: Callable[..., list[dict]] = list_projects_with_status,
          sleep_fn: Callable[[float], None] = time.sleep) -> dict:
    journal_path = journal_path.resolve()
    if journal_path.exists():
        old = json.loads(journal_path.read_text())
        if old.get("phase") != "RESTORED":
            raise RuntimeError("unfinished or active signal probe journal already exists")
        raise RuntimeError("restored journal is immutable; use a new journal path")
    if not CONTAINER_NAME.fullmatch(normal_name) or not CONTAINER_NAME.fullmatch(probe_name):
        raise ValueError("invalid SQCLI container name")
    normal = _inspect(runner, normal_name)
    if normal is None or normal.get("State", {}).get("Running") is not True:
        raise RuntimeError("normal SQCLI container must be running before probe start")
    if _inspect(runner, probe_name) is not None:
        raise RuntimeError("signal probe container name already exists")
    rows = list_fn(base_url)
    running = _running_projects(rows)
    if running:
        raise RuntimeError(f"SQCLI has running projects: {running}")
    build, jar = _validate_build_receipt(build_receipt_path)
    output_dir, container_log = _safe_output(output_dir, raw_log_path)
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("signal probe output path is not a directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    if raw_log_path.resolve().exists():
        raise ValueError("new signal probe requires an absent raw log")
    command = build_run_command(
        normal=normal, probe_name=probe_name, jar=jar,
        output_dir=output_dir, container_log_path=container_log)
    journal = {
        "schema_version": 1, "phase": "PREPARED", "created_at": _now(),
        "normal_container": normal_name, "probe_container": probe_name,
        "normal_was_running": True, "normal_container_id": normal.get("Id"),
        "image_id": normal.get("Image"),
        "build_receipt_path": str(build_receipt_path.resolve()),
        "build_receipt_sha256": _sha(build_receipt_path.resolve()),
        "probe_jar_sha256": build["output_jar_sha256"],
        "output_dir": str(output_dir), "raw_log_path": str(raw_log_path.resolve()),
        "container_log_path": container_log,
        "normal_stopped": False, "probe_created": False,
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(journal_path, journal)
    try:
        _completed(runner, ["docker", "stop", normal_name], timeout=60)
        journal.update({"phase": "NORMAL_STOPPED", "normal_stopped": True,
                        "normal_stopped_at": _now()})
        write_atomic(journal_path, journal)
        created = _completed(runner, command, timeout=60).stdout.strip()
        journal.update({"phase": "PROBE_STARTING", "probe_created": True,
                        "probe_container_id": created, "probe_started_at": _now()})
        write_atomic(journal_path, journal)
        probe_rows = _wait_healthy(
            base_url, list_fn=list_fn, sleep_fn=sleep_fn)
        if _running_projects(probe_rows):
            raise RuntimeError("new signal probe unexpectedly has running projects")
        runtime = inspect_signal_probe_runtime(
            container=probe_name, build_receipt_path=build_receipt_path,
            raw_log_path=raw_log_path, runner=runner)
        journal.update({
            "phase": "PROBE_READY", "probe_ready_at": _now(),
            "probe_runtime": runtime, "project_count": len(probe_rows),
        })
        write_atomic(journal_path, journal)
        return journal
    except Exception as original:
        try:
            _restore_from_journal(journal_path=journal_path, runner=runner,
                                  list_fn=list_fn, sleep_fn=sleep_fn,
                                  base_url=base_url, require_probe_idle=False)
        except Exception as restore_error:
            raise RuntimeError(
                f"probe start failed and automatic restore failed: {restore_error}") from original
        raise


def _restore_from_journal(*, journal_path: Path,
                          runner: Callable[..., subprocess.CompletedProcess],
                          list_fn: Callable[..., list[dict]],
                          sleep_fn: Callable[[float], None], base_url: str,
                          require_probe_idle: bool) -> dict:
    journal_path = journal_path.resolve()
    journal = json.loads(journal_path.read_text())
    if journal.get("schema_version") != 1:
        raise ValueError("invalid signal probe journal")
    if journal.get("phase") == "RESTORED":
        return journal
    normal_name, probe_name = journal.get("normal_container"), journal.get("probe_container")
    if not CONTAINER_NAME.fullmatch(str(normal_name)) or not CONTAINER_NAME.fullmatch(str(probe_name)):
        raise ValueError("journal contains invalid container identity")
    probe = _inspect(runner, probe_name)
    if probe is not None:
        if require_probe_idle and probe.get("State", {}).get("Running") is True:
            running = _running_projects(list_fn(base_url))
            if running:
                raise RuntimeError(f"refusing to restore while probe projects run: {running}")
        if probe.get("State", {}).get("Running") is True:
            _completed(runner, ["docker", "stop", probe_name], timeout=60)
        _completed(runner, ["docker", "rm", probe_name], timeout=30)
    normal = _inspect(runner, normal_name)
    if normal is None:
        raise RuntimeError("normal SQCLI container disappeared; cannot restore")
    if journal.get("normal_was_running") is True and normal.get("State", {}).get("Running") is not True:
        _completed(runner, ["docker", "start", normal_name], timeout=60)
        normal_rows = _wait_healthy(base_url, list_fn=list_fn, sleep_fn=sleep_fn)
        if _running_projects(normal_rows):
            raise RuntimeError("restored normal SQCLI unexpectedly has running projects")
    journal.update({"phase": "RESTORED", "restored_at": _now(),
                    "probe_removed": True, "normal_restored": True})
    write_atomic(journal_path, journal)
    return journal


def restore(*, journal_path: Path, base_url: str = "http://127.0.0.1:8080",
            runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
            list_fn: Callable[..., list[dict]] = list_projects_with_status,
            sleep_fn: Callable[[float], None] = time.sleep) -> dict:
    return _restore_from_journal(
        journal_path=journal_path, runner=runner, list_fn=list_fn,
        sleep_fn=sleep_fn, base_url=base_url, require_probe_idle=True)


def capture_retest(
        *, journal_path: Path, capture_receipt_path: Path,
        build_receipt_path: Path, output_dir: Path, raw_log_path: Path,
        cfx_path: Path, manifest_path: Path, retest_output_dir: Path,
        projects_root: Path = Path("/mnt/volume-SQ/user/projects"),
        normal_name: str = "sqcli-docker", probe_name: str = "sqcli-signal-probe",
        base_url: str = "http://127.0.0.1:8080",
        interval: int = 2, timeout_seconds: int = 1800,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        list_fn: Callable[..., list[dict]] = list_projects_with_status,
        sleep_fn: Callable[[float], None] = time.sleep,
        supervised_fn: Callable[..., dict] = supervised_retest,
        verify_fn: Callable[..., dict] = verify_retest_receipt) -> dict:
    """Start/resume probe Retest; restore normal SQ only after verified completion."""
    journal_path, capture_receipt_path = journal_path.resolve(), capture_receipt_path.resolve()
    retest_receipt_path = retest_output_dir.resolve() / "supervised_retest_receipt.json"

    def completed_capture() -> dict:
        value = json.loads(capture_receipt_path.read_text())
        journal = Path(value.get("journal_path", "")).resolve()
        retest_path = Path(value.get("supervised_retest_receipt_path", "")).resolve()
        if (value.get("decision") != "PASS_SIGNAL_PROBE_RETEST_CAPTURE"
                or journal != journal_path or retest_path != retest_receipt_path
                or not journal.is_file() or not retest_path.is_file()
                or value.get("journal_sha256") != _sha(journal)
                or value.get("supervised_retest_receipt_sha256") != _sha(retest_path)
                or json.loads(journal.read_text()).get("phase") != "RESTORED"):
            raise ValueError("completed signal probe capture receipt invalid")
        retest = json.loads(retest_path.read_text())
        verify_fn(retest_path, candidate_id=retest.get("candidate_id"),
                  orders_path=Path(retest.get("orders_csv_path", "")))
        return value

    if capture_receipt_path.is_file():
        return completed_capture()
    if not journal_path.exists():
        start(
            journal_path=journal_path, build_receipt_path=build_receipt_path,
            output_dir=output_dir, raw_log_path=raw_log_path,
            normal_name=normal_name, probe_name=probe_name, base_url=base_url,
            runner=runner, list_fn=list_fn, sleep_fn=sleep_fn)
    else:
        journal = json.loads(journal_path.read_text())
        if journal.get("phase") == "PROBE_READY":
            current = status(journal_path=journal_path, runner=runner)
            if current.get("probe_running") is not True or current.get("normal_running") is True:
                raise RuntimeError("probe journal cannot be resumed from current Docker state")
            inspect_signal_probe_runtime(
                container=probe_name, build_receipt_path=build_receipt_path,
                raw_log_path=raw_log_path, runner=runner)
        elif journal.get("phase") != "RESTORED" or not retest_receipt_path.is_file():
            raise RuntimeError("probe journal requires explicit recovery before capture resume")

    journal = json.loads(journal_path.read_text())
    retest = None
    if journal.get("phase") == "PROBE_READY":
        # Deliberately no finally-restore here. If the supervising Python process
        # fails while SQ keeps running, the immutable start receipts and live
        # probe are the only safe way to resume without discarding hours.
        retest = supervised_fn(
            cfx_path=cfx_path, manifest_path=manifest_path,
            output_dir=retest_output_dir, base_url=base_url,
            container=probe_name, projects_root=projects_root,
            interval=interval, timeout_seconds=timeout_seconds,
            runner=runner, sleep_fn=sleep_fn,
            signal_probe_build_receipt=build_receipt_path,
            signal_probe_raw_log=raw_log_path)
        verify_fn(retest_receipt_path, candidate_id=retest["candidate_id"],
                  orders_path=Path(retest["orders_csv_path"]))
        restore(journal_path=journal_path, base_url=base_url, runner=runner,
                list_fn=list_fn, sleep_fn=sleep_fn)
    else:
        retest = json.loads(retest_receipt_path.read_text())
        verify_fn(retest_receipt_path, candidate_id=retest.get("candidate_id"),
                  orders_path=Path(retest.get("orders_csv_path", "")))
    final_journal = json.loads(journal_path.read_text())
    if final_journal.get("phase") != "RESTORED":
        raise RuntimeError("normal SQCLI was not restored after probe Retest")
    result = {
        "schema_version": 1,
        "decision": "PASS_SIGNAL_PROBE_RETEST_CAPTURE",
        "candidate_id": retest["candidate_id"],
        "journal_path": str(journal_path), "journal_sha256": _sha(journal_path),
        "supervised_retest_receipt_path": str(retest_receipt_path),
        "supervised_retest_receipt_sha256": _sha(retest_receipt_path),
        "probe_restored": True, "normal_sqcli_healthy": True,
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(capture_receipt_path, result)
    return result


def status(*, journal_path: Path,
           runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict:
    journal_path = journal_path.resolve()
    if not journal_path.is_file():
        return {"status": "NO_JOURNAL", "journal_path": str(journal_path)}
    journal = json.loads(journal_path.read_text())
    normal = _inspect(runner, str(journal.get("normal_container", "")))
    probe = _inspect(runner, str(journal.get("probe_container", "")))
    return {
        "status": journal.get("phase"), "journal_path": str(journal_path),
        "normal_running": normal is not None and normal.get("State", {}).get("Running") is True,
        "probe_running": probe is not None and probe.get("State", {}).get("Running") is True,
        "raw_log_exists": Path(journal.get("raw_log_path", "")).is_file(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--journal", required=True, type=Path)
    start_parser.add_argument("--build-receipt", required=True, type=Path)
    start_parser.add_argument("--output-dir", required=True, type=Path)
    start_parser.add_argument("--raw-log", required=True, type=Path)
    start_parser.add_argument("--normal-container", default="sqcli-docker")
    start_parser.add_argument("--probe-container", default="sqcli-signal-probe")
    for name in ("status", "restore"):
        command = sub.add_parser(name)
        command.add_argument("--journal", required=True, type=Path)
    capture = sub.add_parser("capture-retest")
    capture.add_argument("--journal", required=True, type=Path)
    capture.add_argument("--capture-receipt", required=True, type=Path)
    capture.add_argument("--build-receipt", required=True, type=Path)
    capture.add_argument("--output-dir", required=True, type=Path)
    capture.add_argument("--raw-log", required=True, type=Path)
    capture.add_argument("--cfx", required=True, type=Path)
    capture.add_argument("--manifest", required=True, type=Path)
    capture.add_argument("--retest-output-dir", required=True, type=Path)
    capture.add_argument("--projects-root", type=Path,
                         default=Path("/mnt/volume-SQ/user/projects"))
    capture.add_argument("--normal-container", default="sqcli-docker")
    capture.add_argument("--probe-container", default="sqcli-signal-probe")
    capture.add_argument("--interval", type=int, default=2)
    capture.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    if args.action == "start":
        result = start(
            journal_path=args.journal, build_receipt_path=args.build_receipt,
            output_dir=args.output_dir, raw_log_path=args.raw_log,
            normal_name=args.normal_container, probe_name=args.probe_container)
    elif args.action == "restore":
        result = restore(journal_path=args.journal)
    elif args.action == "capture-retest":
        result = capture_retest(
            journal_path=args.journal, capture_receipt_path=args.capture_receipt,
            build_receipt_path=args.build_receipt, output_dir=args.output_dir,
            raw_log_path=args.raw_log, cfx_path=args.cfx,
            manifest_path=args.manifest, retest_output_dir=args.retest_output_dir,
            projects_root=args.projects_root, normal_name=args.normal_container,
            probe_name=args.probe_container, interval=args.interval,
            timeout_seconds=args.timeout_seconds)
    else:
        result = status(journal_path=args.journal)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
