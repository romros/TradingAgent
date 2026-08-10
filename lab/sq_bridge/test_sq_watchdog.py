import json
from pathlib import Path

from sq_watchdog import Limits, evaluate, gui_snapshot, inventory_sqx, load_limits, run_monitor


def status(generated=1, accepted=0):
    return {
        "observed_at": "2026-08-06T00:00:00+00:00", "project": "P",
        "generated": generated, "in_databank": accepted,
        "memory_available_bytes": 8 * 1024**3, "disk_free_bytes": 8 * 1024**3,
        "artifacts": [], "raw_status": "",
    }


def test_manifest_divides_total_budget_per_isolated_project(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"symbols": ["A", "B", "C"], "attempt_budget": 3000}))
    assert load_limits(manifest).attempt_budget == 1000


def test_manifest_loads_reactive_guard_and_sq_accepted_limit(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "attempt_budget_per_project": 10_000,
        "attempt_stop_guard": 64,
        "accepted_limit": 40,
    }))
    limits = load_limits(manifest)
    assert limits.attempt_control_threshold == 9_936
    assert limits.accepted_target == 40


def test_budget_uses_generated_not_databank():
    assert evaluate(status(1000, 2), [], Limits(1000), 1) == ("BUDGET_REACHED", "ATTEMPT_BUDGET")
    assert evaluate(status(999, 40), [], Limits(1000), 1)[0] == "HEALTHY"


def test_reactive_guard_stops_early_enough_for_inflight_attempts():
    limits = Limits(100, attempt_stop_guard=64)
    assert evaluate(status(35), [], limits, 1)[0] == "SELECTIVE"
    assert evaluate(status(36), [], limits, 1) == ("BUDGET_REACHED", "ATTEMPT_BUDGET")


def test_irregular_acceptance_is_not_false_stall():
    history = [status(10, 0), status(25, 0), status(50, 1)]
    assert evaluate(status(71, 1), history, Limits(1000, stagnation_attempts=500), 500)[0] == "HEALTHY"


def test_inventory_is_deterministic_and_hashed(tmp_path):
    artifact = tmp_path / "Results" / "a.sqx"
    artifact.parent.mkdir()
    artifact.write_bytes(b"candidate")
    first = inventory_sqx(tmp_path)
    second = inventory_sqx(tmp_path)
    assert first == second
    assert first[0]["sha256"] == "dda18a0e21ae47c53b4309434cbc02ae8bf764fa83a6defbb719431242722aa7"


def test_monitor_is_read_only_by_default(tmp_path):
    calls = []
    result = run_monitor(
        base_url="http://sq", project="P", limits=Limits(1000),
        status_file=tmp_path / "latest.json", journal_file=tmp_path / "journal.jsonl",
        disk_path=tmp_path, artifacts=None, interval=1, allow_control=False, once=True,
        snapshot_fn=lambda *_: status(1000), call_fn=lambda *args: calls.append(args),
    )
    assert result["reason"] == "ATTEMPT_BUDGET"
    assert calls == []
    assert len((tmp_path / "journal.jsonl").read_text().splitlines()) == 1


def test_control_requires_opt_in_and_is_audited(tmp_path):
    calls = []
    run_monitor(
        base_url="http://sq", project="P", limits=Limits(1000),
        status_file=tmp_path / "latest.json", journal_file=tmp_path / "journal.jsonl",
        disk_path=tmp_path, artifacts=None, interval=1, allow_control=True, once=True,
        snapshot_fn=lambda *_: status(1001), call_fn=lambda *args: calls.append(args) or "ok",
    )
    assert [call[1].split()[1] for call in calls] == ["action=pause", "action=stop"]
    assert json.loads((tmp_path / "journal.jsonl").read_text().splitlines()[-1])["event"] == "CONTROL_APPLIED"


def test_terminal_snapshot_is_replaced_by_exact_persisted_sq_log(tmp_path):
    result = run_monitor(
        base_url="http://sq", project="P", limits=Limits(100),
        status_file=tmp_path / "latest.json", journal_file=tmp_path / "journal.jsonl",
        disk_path=tmp_path, artifacts=None, interval=1, allow_control=True, once=True,
        snapshot_fn=lambda *_: status(101, 2), call_fn=lambda *_: "ok",
        final_stats_fn=lambda _: {
            "generated": 107, "accepted": 3, "rejected": 104,
            "log_path": "/inside/global.log", "log_sha256": "a" * 64,
            "log_text": "TASK FINISHED\nStrategies generated: 107, Accepted: 3, Rejected: 104\n",
            "attempt_counter_source": "sq_project_final_log"})
    assert result["generated"] == 107
    assert result["attempt_counter_source"] == "sq_project_final_log"
    assert Path(result["sq_final_log_path"]).read_text().startswith("TASK FINISHED")
    assert json.loads((tmp_path / "latest.json").read_text())["generated"] == 107


def test_final_log_is_retried_while_sq_finishes_stopping(tmp_path, monkeypatch):
    attempts = []
    monkeypatch.setattr("sq_watchdog.time.sleep", lambda *_: None)

    def finalizer(_):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("not finished yet")
        return {
            "generated": 90, "accepted": 2, "rejected": 88,
            "log_path": "/inside/global.log", "log_sha256": "a" * 64,
            "log_text": "TASK FINISHED\nStrategies generated: 90, Accepted: 2, Rejected: 88\n",
            "attempt_counter_source": "sq_project_final_log"}

    result = run_monitor(
        base_url="http://sq", project="P", limits=Limits(100, attempt_stop_guard=10),
        status_file=tmp_path / "latest.json", journal_file=tmp_path / "journal.jsonl",
        disk_path=tmp_path, artifacts=None, interval=1, allow_control=True, once=True,
        snapshot_fn=lambda *_: status(90, 2), call_fn=lambda *_: "ok",
        final_stats_fn=finalizer, final_stats_timeout_seconds=1)
    assert len(attempts) == 3
    assert result["generated"] == 90


def test_monitor_error_cannot_control_sq(tmp_path):
    calls = []
    result = run_monitor(
        base_url="http://sq", project="P", limits=Limits(1000),
        status_file=tmp_path / "latest.json", journal_file=tmp_path / "journal.jsonl",
        disk_path=tmp_path, artifacts=None, interval=1, allow_control=True, once=True,
        snapshot_fn=lambda *_: (_ for _ in ()).throw(ConnectionError("offline")),
        call_fn=lambda *args: calls.append(args),
    )
    assert result["reason"] == "MONITOR_ERROR"
    assert calls == []


def test_started_project_natural_stop_is_finalized_without_redundant_control(tmp_path):
    calls = []
    result = run_monitor(
        base_url="http://sq", project="P", limits=Limits(100),
        status_file=tmp_path / "latest.json", journal_file=tmp_path / "journal.jsonl",
        disk_path=tmp_path, artifacts=None, interval=1, allow_control=True, once=True,
        snapshot_fn=lambda *_: {**status(None, 2), "running_status": 0},
        call_fn=lambda *args: calls.append(args), started_project=True,
        final_stats_fn=lambda _: {
            "generated": 81, "accepted": 2, "rejected": 79,
            "log_path": "/inside/global.log", "log_sha256": "a" * 64,
            "log_text": "TASK FINISHED\nStrategies generated: 81, Accepted: 2, Rejected: 79\n",
            "attempt_counter_source": "sq_project_final_log"})
    assert result["reason"] == "SQ_PROJECT_STOPPED"
    assert result["generated"] == 81
    assert calls == []


def test_repeated_monitor_errors_stop_a_started_run(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("sq_watchdog.time.sleep", lambda *_: None)
    result = run_monitor(
        base_url="http://sq", project="P", limits=Limits(100),
        status_file=tmp_path / "latest.json", journal_file=tmp_path / "journal.jsonl",
        disk_path=tmp_path, artifacts=None, interval=1, allow_control=True,
        snapshot_fn=lambda *_: (_ for _ in ()).throw(ConnectionError("offline")),
        call_fn=lambda *args: calls.append(args) or "ok", started_project=True,
        final_stats_fn=lambda _: {
            "generated": 20, "accepted": 0, "rejected": 20,
            "log_path": "/inside/global.log", "log_sha256": "a" * 64,
            "log_text": "TASK FINISHED\nStrategies generated: 20, Accepted: 0, Rejected: 20\n",
            "attempt_counter_source": "sq_project_final_log"})
    assert result["reason"] == "MONITOR_ERROR_BUDGET"
    assert len(calls) == 2


def test_gui_snapshot_maps_single_task_stats_without_text_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr("sq_watchdog.gui_project_stats", lambda *_: {
        "projectName": "P", "strategies": 5, "runningStatus": 1,
        "tasksIterations": [{"taskName": "Build", "iterations": 2}],
        "_engine": {"totalJobsDone": 200}})
    value = gui_snapshot("http://sq:8080", "P", tmp_path)
    assert value["generated"] == 200
    assert value["in_databank"] == 5
    assert value["accepted_pct"] == 2.5
    assert value["running_status"] == 1
    assert value["task_iterations"] == 2
    assert value["attempt_counter_source"] == "engine.totalJobsDone_live_lower_bound"
    assert value["status_source"] == "sq_gui_subscribed_websocket"
