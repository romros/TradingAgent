#!/usr/bin/env python3
"""Transports for the SQCLI HTTP command endpoint."""
from __future__ import annotations

import re
import asyncio
import hashlib
import gzip
import json
import subprocess
import urllib.parse
import urllib.request
import time
from typing import Callable

import websockets


CONTAINER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SAFE_PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
CONTAINER_IMPORT_PATH = re.compile(r"^/tmp/[A-Za-z0-9][A-Za-z0-9_.-]*\.cfx$")
PROJECT_COMMAND = re.compile(
    r"^-project action=(pause|resume|stop) name=(.+)$")
PROJECT_CHANNELS = ("engine-channel", "progress-channel")
DOCKER_HTTP_SCRIPT = r'''set -eu
encoded=$1
port=$2
exec 3<>/dev/tcp/127.0.0.1/$port
printf 'GET /call?cmd=%s HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n' "$encoded" >&3
cat <&3
'''


def docker_exec_http_call(
    container: str, command: str, *, api_port: int = 5050,
    timeout_seconds: int = 20,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> str:
    """Call the loopback-only SQCLI API without exposing its port on the host."""
    if not CONTAINER_NAME.fullmatch(container):
        raise ValueError("invalid SQCLI container name")
    if (not isinstance(api_port, int) or isinstance(api_port, bool)
            or not 1 <= api_port <= 65535):
        raise ValueError("invalid SQCLI API port")
    if not isinstance(command, str) or not command or "\r" in command or "\n" in command:
        raise ValueError("invalid SQCLI command")
    # SQ's /call handler parses the command itself and does not decode escaped
    # path separators inside argument values. Keep `/` literal while encoding
    # query delimiters, whitespace and control characters.
    encoded = urllib.parse.quote(command, safe="=/_-.")
    completed = runner(
        ["docker", "exec", container, "bash", "-c", DOCKER_HTTP_SCRIPT,
         "sqcli-http", encoded, str(api_port)],
        capture_output=True, text=True, timeout=timeout_seconds, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()[-500:]
        raise RuntimeError(f"SQCLI docker transport failed: {detail}")
    raw = completed.stdout
    head, separator, body = raw.partition("\r\n\r\n")
    if not separator:
        # subprocess(text=True) applies universal newline translation on Linux.
        head, separator, body = raw.partition("\n\n")
    if not separator:
        raise RuntimeError("SQCLI returned an invalid HTTP response")
    first = head.splitlines()[0] if head else ""
    match = re.fullmatch(r"HTTP/\d(?:\.\d)?\s+(\d{3})(?:\s+.*)?", first)
    if match is None or int(match.group(1)) != 200:
        raise RuntimeError(f"SQCLI returned HTTP status: {first}")
    return body


def parse_project_final_log(text: str) -> dict:
    """Derive exact counters from a completed SQ global project log."""
    if not isinstance(text, str) or "TASK FINISHED" not in text:
        raise RuntimeError("SQCLI latest project run is not finished")
    rows = re.findall(
        r"Strategies generated:\s*(\d+).*?Accepted:\s*(\d+),\s*Rejected:\s*(\d+)",
        text, re.DOTALL)
    if not rows:
        raise RuntimeError("SQCLI final strategy counters missing")
    generated, accepted, rejected = map(int, rows[-1])
    if generated < 1 or accepted + rejected != generated:
        raise RuntimeError("SQCLI final strategy counters inconsistent")
    return {"generated": generated, "accepted": accepted, "rejected": rejected}


def docker_project_final_log(
    container: str, project: str, *, timeout_seconds: int = 20,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    """Read the newest project log, accepting only a naturally finished SQ task."""
    if not CONTAINER_NAME.fullmatch(container):
        raise ValueError("invalid SQCLI container name")
    if not isinstance(project, str) or not SAFE_PROJECT_NAME.fullmatch(project):
        raise ValueError("invalid SQCLI project name")
    log_dir = f"/home/squser/SQ/user/projects/{project}/log"
    listed = runner(
        ["docker", "exec", container, "find", log_dir, "-maxdepth", "1",
         "-type", "f", "-name", "global_log_*.log", "-printf", "%T@ %p\n"],
        capture_output=True, text=True, timeout=timeout_seconds, check=False)
    if listed.returncode != 0:
        raise RuntimeError("SQCLI project log listing failed")
    candidates = []
    for line in listed.stdout.splitlines():
        stamp, separator, path = line.partition(" ")
        if separator and path.startswith(log_dir + "/"):
            try:
                candidates.append((float(stamp), path))
            except ValueError:
                continue
    if not candidates:
        raise RuntimeError("SQCLI project has no run log")
    log_path = max(candidates)[1]
    completed = runner(
        ["docker", "exec", container, "cat", log_path], capture_output=True,
        text=True, timeout=timeout_seconds, check=False)
    if completed.returncode != 0:
        raise RuntimeError("SQCLI project log read failed")
    text = completed.stdout
    if "TASK FINISHED" not in text:
        raise RuntimeError("SQCLI latest project run is not finished")
    return {
        "log_path": log_path,
        "log_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "log_text": text,
        "completion_source": "sq_project_final_log",
    }


def docker_project_final_stats(
    container: str, project: str, *, timeout_seconds: int = 20,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    """Read the newest completed Build log and derive exact final counters."""
    final = docker_project_final_log(
        container, project, timeout_seconds=timeout_seconds, runner=runner)
    return {
        **parse_project_final_log(final["log_text"]), **final,
        "attempt_counter_source": "sq_project_final_log",
    }


def select_project_stats(payload: object, project: str) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("customProjectStats"), list):
        raise ValueError("SQCLI websocket payload has no project stats")
    matches = [row for row in payload["customProjectStats"]
               if isinstance(row, dict) and row.get("projectName") == project]
    if len(matches) != 1:
        raise ValueError(f"SQCLI project stats not unique: {project}")
    row = matches[0]
    tasks = row.get("tasksIterations")
    if not isinstance(tasks, list) or len(tasks) != 1:
        raise ValueError("Alquimia watchdog requires exactly one SQ task")
    iteration = tasks[0].get("iterations") if isinstance(tasks[0], dict) else None
    for value, label in ((iteration, "iterations"), (row.get("strategies"), "strategies"),
                         (row.get("runningStatus"), "runningStatus")):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"invalid SQCLI project {label}")
    return row


def project_listing(base_url: str, project: str,
                    *, timeout_seconds: int = 15,
                    opener: Callable[..., object] = urllib.request.urlopen) -> dict:
    with opener(f"{base_url.rstrip('/')}/taskmanager/listProjects",
                timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    projects = payload.get("projects") if isinstance(payload, dict) else None
    matches = [row for row in projects or []
               if isinstance(row, dict) and row.get("projectName") == project]
    if len(matches) != 1:
        raise ValueError(f"SQCLI project listing not unique: {project}")
    return matches[0]


def list_projects(base_url: str, *, timeout_seconds: int = 15,
                  opener: Callable[..., object] = urllib.request.urlopen) -> list[dict]:
    with opener(f"{base_url.rstrip('/')}/taskmanager/listProjects",
                timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    projects = payload.get("projects") if isinstance(payload, dict) else None
    if not isinstance(projects, list) or any(not isinstance(row, dict) for row in projects):
        raise RuntimeError("SQCLI returned an invalid project listing")
    return projects


def gui_open_project(base_url: str, container_path: str,
                     *, timeout_seconds: int = 30,
                     opener: Callable[..., object] = urllib.request.urlopen) -> dict:
    if (not isinstance(container_path, str)
            or not CONTAINER_IMPORT_PATH.fullmatch(container_path)):
        raise ValueError("invalid SQCLI import path")
    query = urllib.parse.urlencode({"file": container_path, "loadAsIs": "true"})
    with opener(f"{base_url.rstrip('/')}/taskmanager/openProject?{query}",
                timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("success") is None:
        raise RuntimeError(f"SQCLI project import failed: {payload}")
    return payload


def gui_start_project(base_url: str, project: str, *, timeout_seconds: int = 30,
                      opener: Callable[..., object] = urllib.request.urlopen) -> dict:
    if not isinstance(project, str) or not SAFE_PROJECT_NAME.fullmatch(project):
        raise ValueError("invalid SQCLI project name")
    data = gzip.compress(urllib.parse.urlencode({"projectName": project}).encode())
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/project/start", data=data,
        headers={"Content-Type": "application/json; charset=x-user-defined-binary",
                 "Content-Encoding": "gzip"}, method="POST")
    with opener(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("success") is None:
        raise RuntimeError(f"SQCLI project start failed: {payload}")
    return payload


def trigger_project_listing(base_url: str, project: str,
                            *, timeout_seconds: int = 15,
                            opener: Callable[..., object] = urllib.request.urlopen) -> None:
    """Backward-compatible existence check used by older callers."""
    project_listing(base_url, project, timeout_seconds=timeout_seconds, opener=opener)


async def _gui_project_stats(base_url: str, project: str, timeout_seconds: float) -> dict:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid SQCLI GUI base URL")
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    port = f":{parsed.port}" if parsed.port else ""
    websocket_url = f"{ws_scheme}://{parsed.hostname}{port}/websocket/updates"
    deadline = time.monotonic() + timeout_seconds
    async with websockets.connect(websocket_url) as socket:
        await socket.send(json.dumps({"action": "setup", "app": "TASKMANAGER"}))
        # This is the same explicit subscription used by SQ's own project
        # control panel.  It causes the server to send a projectData snapshot
        # and, on current SQX builds, the TaskManager iteration counters.
        for channel in PROJECT_CHANNELS:
            await socket.send(json.dumps({
                "action": "subscribe", "projectName": project, "channel": channel,
            }))
        selected = None
        engine = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                listing = await asyncio.to_thread(project_listing, base_url, project)
                return {**listing, "_engine": engine or {}, "tasksIterations": None}
            try:
                raw = await asyncio.wait_for(socket.recv(), remaining)
            except TimeoutError:
                # A stopped/idle SQ server can keep this channel silent.  REST
                # still proves project identity and persisted databank size;
                # return degraded telemetry instead of fabricating attempts.
                listing = await asyncio.to_thread(project_listing, base_url, project)
                return {**listing, "_engine": engine or {}, "tasksIterations": None}
            payload = json.loads(raw)
            if isinstance(payload, dict) and "customProjectStats" in payload:
                selected = select_project_stats(payload, project)
            project_data = payload.get("projectData") if isinstance(payload, dict) else None
            if isinstance(project_data, dict) and project_data.get("name") == project:
                channels = project_data.get("channels")
                for item in channels if isinstance(channels, list) else []:
                    if isinstance(item, dict) and item.get("name") == "engine-channel":
                        candidate = item.get("data")
                        if isinstance(candidate, dict) and candidate.get("projectName") == project:
                            engine = candidate
            if selected is not None and engine is not None:
                return {**selected, "_engine": engine}
            # SQ doesn't periodically emit TaskManager counters when every
            # project is stopped.  The subscribed engine snapshot is still an
            # authoritative liveness/status check, but it must not invent a
            # historical attempt counter.
            if engine is not None and engine.get("runningStatus") == 0:
                listing = await asyncio.to_thread(project_listing, base_url, project)
                return {**listing, "runningStatus": 0, "_engine": engine,
                        "tasksIterations": None}


def gui_project_stats(base_url: str, project: str, *, timeout_seconds: float = 45) -> dict:
    return asyncio.run(_gui_project_stats(base_url, project, timeout_seconds))


def gui_project_action(base_url: str, action: str, project: str,
                       *, timeout_seconds: int = 20,
                       opener: Callable[..., object] = urllib.request.urlopen) -> str:
    if action not in {"pause", "resume", "stop"}:
        raise ValueError("unsupported SQCLI GUI project action")
    if not isinstance(project, str) or not project or "\r" in project or "\n" in project:
        raise ValueError("invalid SQCLI project name")
    query = urllib.parse.urlencode({"projectName": project})
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/project/{action}?{query}", method="GET")
    with opener(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if (not isinstance(payload, dict) or payload.get("success") is False
            or payload.get("success") is None):
        raise RuntimeError(f"SQCLI GUI action failed: {payload}")
    return json.dumps(payload, sort_keys=True)


def gui_project_action_from_cli(base_url: str, command: str) -> str:
    match = PROJECT_COMMAND.fullmatch(command)
    if match is None:
        raise ValueError("unsupported SQCLI project command for GUI transport")
    return gui_project_action(base_url, match.group(1), match.group(2))
