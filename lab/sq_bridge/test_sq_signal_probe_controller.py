import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from lab.sq_bridge.sq_signal_probe_build import SUPPORTED_SIGNAL_SOURCE_SHA256
from lab.sq_bridge.sq_signal_probe_controller import (
    MACHINE_ID, NORMAL_INTERNAL, NORMAL_USER, PROBE_JAR,
    build_run_command, capture_retest, restore, start, status,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normal(tmp_path: Path) -> dict:
    user = tmp_path / "user"; user.mkdir()
    internal = tmp_path / "internal"; internal.mkdir()
    machine = tmp_path / "machine-id"; machine.write_text("machine")
    return {
        "Id": "normal-id", "Name": "/sqcli-docker", "Image": "sha256:image",
        "State": {"Running": True}, "Config": {"User": "squser"},
        "HostConfig": {"Memory": 15_000, "MemorySwap": 30_000,
                       "NanoCpus": 6_000_000_000},
        "Mounts": [
            {"Type": "bind", "Source": str(user),
             "Destination": NORMAL_USER, "RW": True},
            {"Type": "bind", "Source": str(internal),
             "Destination": NORMAL_INTERNAL, "RW": True},
            {"Type": "bind", "Source": str(machine),
             "Destination": MACHINE_ID, "RW": False},
        ],
    }


def _build(tmp_path: Path) -> tuple[Path, Path]:
    jar = tmp_path / "probe.jar"; jar.write_bytes(b"probe")
    receipt = tmp_path / "build.json"
    receipt.write_text(json.dumps({
        "decision": "PASS_SIGNAL_PROBE_JAR", "production_sq_modified": False,
        "source_sha256": next(iter(SUPPORTED_SIGNAL_SOURCE_SHA256)),
        "java_class_major_version": 66,
        "output_jar_path": str(jar), "output_jar_sha256": _sha(jar),
        "log_environment_variable": "ALQUIMIA_SIGNAL_LOG_PATH",
    }))
    return receipt, jar


def _probe(normal: dict, jar: Path, output: Path, running=True) -> dict:
    return {
        "Id": "probe-id", "Name": "/sqcli-signal-probe", "Image": normal["Image"],
        "State": {"Running": running},
        "Config": {"Env": ["ALQUIMIA_SIGNAL_LOG_PATH=/probe/raw.log"]},
        "Mounts": [
            {"Type": "bind", "Source": str(jar),
             "Destination": PROBE_JAR, "RW": False},
            {"Type": "bind", "Source": str(output),
             "Destination": "/probe", "RW": True},
        ],
    }


class DockerFake:
    def __init__(self, normal, jar, output, fail_run=False):
        self.containers = {"sqcli-docker": normal}
        self.jar, self.output, self.fail_run = jar, output, fail_run
        self.calls = []

    def __call__(self, args, **_kwargs):
        self.calls.append(args)
        if args[:2] == ["docker", "inspect"]:
            value = self.containers.get(args[2])
            return subprocess.CompletedProcess(
                args, 0 if value else 1, json.dumps([value]) if value else "",
                "" if value else "error: no such object")
        if args[:2] == ["docker", "stop"]:
            self.containers[args[2]]["State"]["Running"] = False
            return subprocess.CompletedProcess(args, 0, args[2], "")
        if args[:2] == ["docker", "start"]:
            self.containers[args[2]]["State"]["Running"] = True
            return subprocess.CompletedProcess(args, 0, args[2], "")
        if args[:2] == ["docker", "rm"]:
            self.containers.pop(args[2], None)
            return subprocess.CompletedProcess(args, 0, args[2], "")
        if args[:3] == ["docker", "run", "-d"]:
            if self.fail_run:
                return subprocess.CompletedProcess(args, 1, "", "failed")
            self.containers["sqcli-signal-probe"] = _probe(
                self.containers["sqcli-docker"], self.jar, self.output)
            return subprocess.CompletedProcess(args, 0, "probe-id\n", "")
        raise AssertionError(args)


def test_run_command_isolated_read_only_and_inherits_resource_limits(tmp_path):
    normal = _normal(tmp_path); _, jar = _build(tmp_path)
    output = tmp_path / "out"; output.mkdir()
    command = build_run_command(
        normal=normal, probe_name="sqcli-signal-probe", jar=jar,
        output_dir=output, container_log_path="/probe/raw.log")
    joined = " ".join(command)
    assert "--cpus 6" in joined and "--memory 15000" in joined
    assert f"src={normal['Mounts'][1]['Source']},dst={NORMAL_INTERNAL},readonly" in joined
    assert f"src={jar},dst={PROBE_JAR},readonly" in joined
    assert "127.0.0.1:8080:8080" in command
    assert command[-2:] == ["sha256:image", "-gui"]


def test_start_and_restore_are_journaled_and_idempotent(tmp_path):
    normal = _normal(tmp_path); receipt, jar = _build(tmp_path)
    output = tmp_path / "output"; output.mkdir()
    fake = DockerFake(normal, jar, output)
    journal = tmp_path / "journal.json"
    started = start(
        journal_path=journal, build_receipt_path=receipt,
        output_dir=output, raw_log_path=output / "raw.log",
        runner=fake, list_fn=lambda _url: [], sleep_fn=lambda _: None)
    assert started["phase"] == "PROBE_READY"
    assert not normal["State"]["Running"]
    assert status(journal_path=journal, runner=fake)["probe_running"] is True
    restored = restore(
        journal_path=journal, runner=fake,
        list_fn=lambda _url: [], sleep_fn=lambda _: None)
    assert restored["phase"] == "RESTORED"
    assert normal["State"]["Running"]
    assert "sqcli-signal-probe" not in fake.containers
    assert restore(journal_path=journal, runner=fake) == restored


def test_status_fails_closed_when_docker_inspection_is_denied(tmp_path):
    journal = tmp_path / "journal.json"
    journal.write_text(json.dumps({
        "phase": "PROBE_READY", "normal_container": "sqcli-docker",
        "probe_container": "sqcli-signal-probe", "raw_log_path": "",
    }))

    def denied(args, **_kwargs):
        return subprocess.CompletedProcess(
            args, 1, "", "permission denied while connecting to Docker socket")

    with pytest.raises(RuntimeError, match="cannot inspect Docker container"):
        status(journal_path=journal, runner=denied)


def test_start_refuses_running_projects_before_any_mutation(tmp_path):
    normal = _normal(tmp_path); receipt, jar = _build(tmp_path)
    output = tmp_path / "output"; output.mkdir()
    fake = DockerFake(normal, jar, output)
    with pytest.raises(RuntimeError, match="running projects"):
        start(
            journal_path=tmp_path / "journal.json", build_receipt_path=receipt,
            output_dir=output, raw_log_path=output / "raw.log", runner=fake,
            list_fn=lambda _url: [{"projectName": "BUSY", "runningStatus": 1}])
    assert not any(call[:2] == ["docker", "stop"] for call in fake.calls)


def test_failed_probe_creation_automatically_restores_normal_service(tmp_path):
    normal = _normal(tmp_path); receipt, jar = _build(tmp_path)
    output = tmp_path / "output"; output.mkdir()
    fake = DockerFake(normal, jar, output, fail_run=True)
    journal = tmp_path / "journal.json"
    with pytest.raises(RuntimeError, match="command failed"):
        start(
            journal_path=journal, build_receipt_path=receipt,
            output_dir=output, raw_log_path=output / "raw.log", runner=fake,
            list_fn=lambda _url: [], sleep_fn=lambda _: None)
    assert normal["State"]["Running"]
    assert json.loads(journal.read_text())["phase"] == "RESTORED"


def test_capture_retest_restores_only_after_verified_completion(tmp_path):
    normal = _normal(tmp_path); receipt, jar = _build(tmp_path)
    output = tmp_path / "output"; output.mkdir()
    fake = DockerFake(normal, jar, output)
    journal, capture = tmp_path / "journal.json", tmp_path / "capture.json"
    retest_dir = tmp_path / "retest"

    def supervised(**kwargs):
        Path(kwargs["signal_probe_raw_log"]).write_text("1;L;1\n")
        retest_dir.mkdir()
        orders = retest_dir / "orders.csv"; orders.write_text("orders\n")
        value = {"candidate_id": "T", "orders_csv_path": str(orders)}
        (retest_dir / "supervised_retest_receipt.json").write_text(json.dumps(value))
        return value

    result = capture_retest(
        journal_path=journal, capture_receipt_path=capture,
        build_receipt_path=receipt, output_dir=output,
        raw_log_path=output / "raw.log", cfx_path=tmp_path / "x.cfx",
        manifest_path=tmp_path / "x.json", retest_output_dir=retest_dir,
        runner=fake, list_fn=lambda _url: [], sleep_fn=lambda _: None,
        supervised_fn=supervised, verify_fn=lambda *_args, **_kwargs: {})
    assert result["decision"] == "PASS_SIGNAL_PROBE_RETEST_CAPTURE"
    assert json.loads(journal.read_text())["phase"] == "RESTORED"
    assert normal["State"]["Running"]
    # Completed capture is replayed without any Docker mutation.
    calls = len(fake.calls)
    assert capture_retest(
        journal_path=journal, capture_receipt_path=capture,
        build_receipt_path=receipt, output_dir=output,
        raw_log_path=output / "raw.log", cfx_path=tmp_path / "x.cfx",
        manifest_path=tmp_path / "x.json", retest_output_dir=retest_dir,
        runner=fake, verify_fn=lambda *_args, **_kwargs: {}) == result
    assert len(fake.calls) == calls


def test_capture_supervisor_interruption_keeps_live_probe_for_resume(tmp_path):
    normal = _normal(tmp_path); receipt, jar = _build(tmp_path)
    output = tmp_path / "output"; output.mkdir()
    fake = DockerFake(normal, jar, output)
    journal, capture = tmp_path / "journal.json", tmp_path / "capture.json"
    attempts = {"count": 0}

    def interrupted(**_kwargs):
        attempts["count"] += 1
        raise RuntimeError("supervisor interrupted")

    common = dict(
        journal_path=journal, capture_receipt_path=capture,
        build_receipt_path=receipt, output_dir=output,
        raw_log_path=output / "raw.log", cfx_path=tmp_path / "x.cfx",
        manifest_path=tmp_path / "x.json", retest_output_dir=tmp_path / "retest",
        runner=fake, list_fn=lambda _url: [], sleep_fn=lambda _: None,
        verify_fn=lambda *_args, **_kwargs: {})
    with pytest.raises(RuntimeError, match="supervisor interrupted"):
        capture_retest(**common, supervised_fn=interrupted)
    assert json.loads(journal.read_text())["phase"] == "PROBE_READY"
    assert fake.containers["sqcli-signal-probe"]["State"]["Running"] is True
    assert normal["State"]["Running"] is False
