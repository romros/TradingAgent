import subprocess

import pytest

from lab.sq_bridge.sqcli_transport import (
    docker_exec_http_call, gui_project_action, project_listing, select_project_stats,
    trigger_project_listing,
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
