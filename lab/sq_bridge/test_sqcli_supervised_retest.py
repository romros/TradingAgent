import shutil
import subprocess
import zipfile
import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.sqcli_supervised_retest import (
    inspect_signal_probe_runtime, parse_retest_final_log, supervised_retest, verify_retest_receipt,
    verify_supervised_retest_receipt,
)
from lab.sq_bridge.alquimia_retest import generate
from lab.sq_bridge.test_alquimia_retest import _fixture, _generate


LOG = """Project: RETEST_T
TASK STARTED
Databanks before start: Results (1), PreHoldout (0)
TASK FINISHED at 2026.08.11 02:00:00 in 2 s.
Databanks after finish: Results (1), PreHoldout (1)
Total tested: 1, Time per strategy: 0 ms., Passed: 0, Failed: 1
"""


def test_retest_log_proves_exact_uncensored_one_candidate_execution():
    assert parse_retest_final_log(LOG) == {
        "input_before": 1, "output_before": 0, "input_after": 1,
        "output_after": 1, "total_tested": 1, "passed": 0, "failed": 1,
    }
    with pytest.raises(ValueError, match="COUNTERS_INVALID"):
        parse_retest_final_log(LOG.replace("Results (1), PreHoldout (0)",
                                          "Results (2), PreHoldout (0)"))
    holdout_log = LOG.replace("PreHoldout", "Holdout")
    assert parse_retest_final_log(holdout_log, "Holdout")["total_tested"] == 1


def test_signal_probe_runtime_requires_exact_read_only_jar_and_writable_log_mount(tmp_path):
    jar = tmp_path / "Snippets.signal-probe.jar"
    jar.write_bytes(b"probe")
    receipt = tmp_path / "build.json"
    receipt.write_text(json.dumps({
        "decision": "PASS_SIGNAL_PROBE_JAR",
        "production_sq_modified": False,
        "output_jar_path": str(jar),
        "output_jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "log_environment_variable": "ALQUIMIA_SIGNAL_LOG_PATH",
    }))
    raw = tmp_path / "probe/raw.log"
    payload = [{
        "Id": "container-id", "State": {"Running": True},
        "Config": {"Env": ["ALQUIMIA_SIGNAL_LOG_PATH=/probe/raw.log"]},
        "Mounts": [
            {"Source": str(jar),
             "Destination": "/home/squser/SQ/internal/libs/Snippets.jar", "RW": False},
            {"Source": str(raw.parent), "Destination": "/probe", "RW": True},
        ],
    }]

    def runner(args, **_kwargs):
        assert args == ["docker", "inspect", "sqcli-signal-probe"]
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    result = inspect_signal_probe_runtime(
        container="sqcli-signal-probe", build_receipt_path=receipt,
        raw_log_path=raw, runner=runner)
    assert result["decision"] == "PASS_SIGNAL_PROBE_RUNTIME"
    assert result["probe_jar_read_only"] is True
    payload[0]["Mounts"][0]["RW"] = True
    with pytest.raises(ValueError, match="MOUNT_MISMATCH"):
        inspect_signal_probe_runtime(
            container="sqcli-signal-probe", build_receipt_path=receipt,
            raw_log_path=raw, runner=runner)


def test_supervised_retest_binds_input_output_log_and_orders_export(tmp_path):
    (tmp_path / "source").mkdir()
    manifest, cfx = _generate(tmp_path / "source")
    manifest_path = cfx.with_suffix(".manifest.json")
    projects_root = tmp_path / "projects"
    project_dir = projects_root / "RETEST_T"
    state = {"imported": False, "started": False, "synced": False,
             "poll": 0, "starts": 0}

    def listing(_base_url):
        if not state["imported"]:
            return []
        running = 0
        if state["started"]:
            state["poll"] += 1
            running = 1 if state["poll"] == 1 else 0
        return [{"projectName": "RETEST_T", "runningStatus": running,
                 "hasUnresolvedResources": False,
                 "strategies": 1 if state["synced"] else 0}]

    def open_project(_base_url, _container_path):
        project_dir.mkdir(parents=True)
        shutil.copyfile(cfx, project_dir / "project.cfx")
        state["imported"] = True
        return {"success": "ok", "projectName": "RETEST_T"}

    def start_project(_base_url, _project):
        state["starts"] += 1
        source_sqx = next((project_dir / "databanks/Results").glob("*.sqx"))
        target = project_dir / "databanks/PreHoldout" / source_sqx.name
        with zipfile.ZipFile(source_sqx) as source, zipfile.ZipFile(target, "w") as output:
            for name in source.namelist():
                output.writestr(name, source.read(name))
            output.writestr("orders.bin", b"observed-orders")
        state["started"] = True
        return {"success": "started"}

    def export_orders(command):
        assert "action=orderstocsv" in command
        output_sqx = next((project_dir / "databanks/PreHoldout").glob("*.sqx"))
        token = hashlib.sha256(output_sqx.read_bytes()).hexdigest()[:16]
        orders = project_dir / f"orders-pre-holdout-{token}.csv"
        orders.write_text(
            '"Ticket";"Type";"Open time";"Open price";"Close time";"Close price"\n'
            '"1";"Buy";"2020.01.02 00:00:00";"1";"2020.01.03 00:00:00";"1.01"\n')
        return "Orders export finished"

    def sync_databank(command):
        assert command == "-databank action=syncfromfiles project=RETEST_T name=Results"
        state["synced"] = True
        return "Databank synced"

    def runner(args, **_kwargs):
        return subprocess.CompletedProcess(args, 0, "", "")

    common = dict(
        cfx_path=cfx, manifest_path=manifest_path,
        output_dir=tmp_path / "evidence", projects_root=projects_root,
        listing_fn=listing, open_fn=open_project, start_fn=start_project,
        final_log_fn=lambda _project: {
            "log_text": LOG, "completion_source": "sq_project_final_log"},
        sync_fn=sync_databank, export_fn=export_orders, runner=runner,
        interval=1, timeout_seconds=10)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        supervised_retest(
            **common,
            sleep_fn=lambda _seconds: (_ for _ in ()).throw(
                RuntimeError("simulated interruption")))
    assert (tmp_path / "evidence/retest_start_receipt.json").is_file()
    result = supervised_retest(**common, sleep_fn=lambda _seconds: None)
    assert result["decision"] == "PASS_SUPERVISED_RETEST"
    assert result["candidate_id"] == "T"
    assert result["candidate_input_sqx_sha256"] == manifest["candidate_sqx_sha256"]
    assert result["total_tested"] == 1
    assert result["failed"] == 1
    # The resumed process proves completion from the final SQ log even though
    # its own first poll happens after the short Retest has stopped.
    assert result["observed_running"] is False
    assert result["holdout_accessed"] is False
    assert result["performance_filters_applied_in_sq"] is False
    assert state["starts"] == 1
    receipt_path = tmp_path / "evidence/supervised_retest_receipt.json"
    assert verify_retest_receipt(
        receipt_path, candidate_id="T",
        orders_path=Path(result["orders_csv_path"])) == result
    replay = supervised_retest(
        cfx_path=cfx, manifest_path=manifest_path,
        output_dir=tmp_path / "evidence", projects_root=projects_root,
        listing_fn=lambda *_: (_ for _ in ()).throw(AssertionError("must replay")))
    assert replay == result


def test_supervised_holdout_records_exactly_one_uncensored_opening(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source, sqx, discovery = _fixture(source_dir)
    discovery_value = json.loads(discovery.read_text())
    discovery_value["holdout_release_authorized"] = True
    discovery_value["campaign_id"] = "campaign"
    discovery.write_text(json.dumps(discovery_value))
    release = source_dir / "small.json"
    release.write_text(json.dumps({
        "stage": "small_account_economics", "decision": "PASS",
        "campaign_id": "campaign", "candidate_ids": ["T"],
        "holdout_accessed": False}))
    cfx = source_dir / "holdout.cfx"
    manifest = generate(
        source=source, output=cfx, project_name="HOLDOUT_T", stage="holdout",
        manifest_path=discovery,
        methodology_path=Path(__file__).with_name("methodology_v4.json"),
        symbol="NVDA", timeframe="M15", candidate_sqx=sqx, candidate_id="T",
        holdout_release_artifact=release)
    manifest_path = cfx.with_suffix(".manifest.json")
    projects_root = tmp_path / "projects"
    project_dir = projects_root / "HOLDOUT_T"
    state = {"imported": False, "started": False, "synced": False}

    def listing(_):
        if not state["imported"]:
            return []
        return [{"projectName": "HOLDOUT_T", "runningStatus": 0,
                 "hasUnresolvedResources": False,
                 "strategies": 1 if state["synced"] else 0}]

    def open_project(_, __):
        project_dir.mkdir(parents=True)
        shutil.copyfile(cfx, project_dir / "project.cfx")
        state["imported"] = True
        return {"success": "ok", "projectName": "HOLDOUT_T"}

    def start_project(_, __):
        source_sqx = next((project_dir / "databanks/Results").glob("*.sqx"))
        target = project_dir / "databanks/Holdout" / source_sqx.name
        with zipfile.ZipFile(source_sqx) as source_archive, zipfile.ZipFile(target, "w") as output:
            for name in source_archive.namelist():
                output.writestr(name, source_archive.read(name))
            output.writestr("orders.bin", b"holdout-orders")
        state["started"] = True
        return {"success": "started"}

    def sync(command):
        assert command.endswith("name=Results")
        state["synced"] = True
        return "synced"

    def export(command):
        assert "orders-holdout-" in command
        output_sqx = next((project_dir / "databanks/Holdout").glob("*.sqx"))
        token = hashlib.sha256(output_sqx.read_bytes()).hexdigest()[:16]
        orders = project_dir / f"orders-holdout-{token}.csv"
        orders.write_text('"Ticket";"Type"\n"1";"Buy"\n')
        return "exported"

    holdout_log = LOG.replace("RETEST_T", "HOLDOUT_T").replace(
        "PreHoldout", "Holdout")
    result = supervised_retest(
        cfx_path=cfx, manifest_path=manifest_path,
        output_dir=tmp_path / "evidence", projects_root=projects_root,
        listing_fn=listing, open_fn=open_project, start_fn=start_project,
        final_log_fn=lambda _: {"log_text": holdout_log,
                                "completion_source": "sq_project_final_log"},
        sync_fn=sync, export_fn=export,
        runner=lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""),
        sleep_fn=lambda _: None, interval=1, timeout_seconds=10)
    assert result["holdout_accessed"] is True
    assert result["holdout_evaluation_count"] == 1
    assert result["retest_stage"] == "holdout"
    receipt = tmp_path / "evidence/supervised_retest_receipt.json"
    assert verify_supervised_retest_receipt(
        receipt, candidate_id="T", orders_path=Path(result["orders_csv_path"]),
        expected_stage="holdout") == result
    assert manifest["performance_filters_applied_in_sq"] is False
