import subprocess
import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.sqcli_transport import (
    docker_exec_http_call, docker_project_final_stats, gui_project_action,
    parse_project_final_log, project_listing, select_project_stats, trigger_project_listing,
)


def test_docker_transport_encodes_command_and_parses_body():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args, 0, "HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\nProject", "")

    assert docker_exec_http_call(
        "sqcli-docker", '-project action=status name="A B"', runner=runner) == "Project"
    assert calls[0][0][-2] == "-project%20action=status%20name=%22A%20B%22"
    assert calls[0][0][-1] == "5050"
    assert calls[0][1]["timeout"] == 20


def test_docker_transport_rejects_injection_and_http_errors():
    with pytest.raises(ValueError, match="container"):
        docker_exec_http_call("bad;name", "-h")
    with pytest.raises(ValueError, match="command"):
        docker_exec_http_call("sqcli", "-h\nstop")

    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "HTTP/1.1 404 Not Found\r\n\r\n", "")

    with pytest.raises(RuntimeError, match="404"):
        docker_exec_http_call("sqcli", "-h", runner=runner)


def test_docker_transport_accepts_universal_newline_translation():
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 0, "HTTP/1.1 200 OK\nContent-Length: 2\n\nOK", "")

    assert docker_exec_http_call("sqcli", "-h", runner=runner) == "OK"


def test_taskmanager_stats_require_exact_project_and_one_task():
    payload = {"customProjectStats": [{"projectName": "P", "strategies": 7,
                "runningStatus": 1, "tasksIterations": [
                    {"taskName": "Build", "iterations": 123}]}]}
    assert select_project_stats(payload, "P")["strategies"] == 7
    payload["customProjectStats"][0]["tasksIterations"].append(
        {"taskName": "Other", "iterations": 0})
    with pytest.raises(ValueError, match="exactly one"):
        select_project_stats(payload, "P")


def test_gui_action_matches_sq_control_panel_get_request_and_requires_success():
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self): return b'{"success":"Stopping project."}'

    def opener(request, **kwargs):
        calls.append((request, kwargs)); return Response()

    gui_project_action("http://sq:8080", "stop", "A B", opener=opener)
    assert calls[0][0].full_url == "http://sq:8080/project/stop?projectName=A+B"
    assert calls[0][0].data is None
    assert calls[0][0].method == "GET"
    assert calls[0][1]["timeout"] == 20

    with pytest.raises(ValueError, match="unsupported"):
        gui_project_action("http://sq:8080", "start", "P", opener=opener)


def test_project_listing_trigger_requires_exact_project():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self): return b'{"projects":[{"projectName":"P"}]}'

    calls = []
    trigger_project_listing(
        "http://sq:8080", "P",
        opener=lambda url, **kwargs: calls.append((url, kwargs)) or Response())
    assert calls == [("http://sq:8080/taskmanager/listProjects", {"timeout": 15})]
    assert project_listing("http://sq:8080", "P", opener=lambda *_1, **_2: Response()) == {
        "projectName": "P"}
    with pytest.raises(ValueError, match="not unique"):
        trigger_project_listing("http://sq:8080", "Q", opener=lambda *_1, **_2: Response())


def test_final_log_parser_requires_completed_consistent_exact_counters():
    log = """TASK FINISHED at 2026.08.10 23:30:18.050 in 32 s.
Strategies generated: 192, Time per strategy: 136 ms., Accepted: 10, Rejected: 182,
"""
    assert parse_project_final_log(log) == {
        "generated": 192, "accepted": 10, "rejected": 182}
    with pytest.raises(RuntimeError, match="not finished"):
        parse_project_final_log(log.replace("TASK FINISHED", "TASK STARTED"))
    with pytest.raises(RuntimeError, match="inconsistent"):
        parse_project_final_log(log.replace("Rejected: 182", "Rejected: 181"))


def test_docker_final_stats_selects_newest_log_without_shell_interpolation():
    calls = []
    log = "TASK FINISHED\nStrategies generated: 12, Accepted: 2, Rejected: 10\n"

    def runner(args, **kwargs):
        calls.append(args)
        if "find" in args:
            return subprocess.CompletedProcess(
                args, 0, "1.0 /logs/ignored\n2.0 /home/squser/SQ/user/projects/P/log/global_log_2.log\n", "")
        return subprocess.CompletedProcess(args, 0, log, "")

    value = docker_project_final_stats("sqcli-docker", "P", runner=runner)
    assert value["generated"] == 12
    assert value["log_text"] == log
    assert calls[1] == ["docker", "exec", "sqcli-docker", "cat",
                        "/home/squser/SQ/user/projects/P/log/global_log_2.log"]
    with pytest.raises(ValueError, match="project"):
        docker_project_final_stats("sqcli-docker", "P;bad", runner=runner)


def test_observed_genetic_budget_smoke_is_bound_to_exact_sq_log():
    root = Path(__file__).with_name("evidence")
    receipt = json.loads((root / "sq_genetic_budget_smoke_20260810.json").read_text())
    log = root / receipt["final"]["log_path"]
    assert hashlib.sha256(log.read_bytes()).hexdigest() == receipt["final"]["log_sha256"]
    assert parse_project_final_log(log.read_text()) == {
        key: receipt["final"][key] for key in ("generated", "accepted", "rejected")}
    assert receipt["decision"] == "REJECT_AS_SCIENTIFIC_RUN"
    assert receipt["candidate_ids_promoted"] == []
