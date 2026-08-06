#!/usr/bin/env python3
"""Run one bounded SQ Builder pilot through the build-143 GUI API."""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import websockets


def http_json(base_url: str, endpoint: str, data: dict | None = None) -> dict:
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    payload = None
    headers = {}
    if data is not None:
        payload = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def project_preflight(projects_response: dict, project: str) -> dict:
    matches = [item for item in projects_response.get("projects", []) if item.get("projectName") == project]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one loaded project named {project}, found {len(matches)}")
    item = matches[0]
    if item.get("hasUnresolvedResources"):
        raise ValueError(f"project has unresolved resources: {project}")
    if item.get("tasks") != 1:
        raise ValueError(f"pilot requires exactly one task, found {item.get('tasks')}")
    return item


def engine_update(message: str, project: str) -> dict | None:
    payload = json.loads(message)
    project_data = payload.get("projectData") or {}
    if project_data.get("name") != project:
        return None
    for channel in project_data.get("channels") or []:
        if channel.get("name") == "engine-channel":
            return channel.get("data") or {}
    return None


def append_jsonl(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


async def run(
    *, gui_url: str, project: str, attempt_budget: int, journal: Path,
    message_timeout: int = 120, allow_control: bool = False, action: str = "start",
) -> dict:
    project_preflight(http_json(gui_url, "taskmanager/listProjects"), project)
    websocket_url = gui_url.replace("http://", "ws://").replace("https://", "wss://")
    websocket_url = f"{websocket_url.rstrip('/')}/websocket/updates"
    started_at = datetime.now(timezone.utc).isoformat()
    latest: dict = {"project": project, "started_at": started_at, "attempt_budget": attempt_budget}

    async with websockets.connect(websocket_url) as socket:
        await socket.send(json.dumps({"action": "setup", "app": "TASKMANAGER"}))
        await socket.send(json.dumps({"action": "subscribe", "projectName": project, "channel": "engine-channel"}))
        if action not in {"start", "resume"}:
            raise ValueError(f"unsupported action: {action}")
        response = http_json(gui_url, f"project/{action}", {"projectName": project})
        if response.get("success") is False:
            raise RuntimeError(f"SQ refused start: {response}")
        append_jsonl(journal, {**latest, "event": f"{action.upper()}_REQUESTED", "response": response})

        while True:
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=message_timeout)
            except TimeoutError:
                latest.update({
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "MONITOR_TIMEOUT",
                })
                if allow_control:
                    latest["pause_response"] = http_json(gui_url, "project/pause", {"projectName": project})
                    latest["control_applied"] = True
                else:
                    latest["control_applied"] = False
                append_jsonl(journal, latest)
                raise RuntimeError("engine channel timed out; project pause requested when authorized")
            update = engine_update(raw, project)
            if update is None:
                continue
            latest = {
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "project": project,
                "attempt_budget": attempt_budget,
                "generated": update.get("totalJobsDone"),
                "accepted": update.get("strategiesAccepted"),
                "rejected": update.get("strategiesRejected"),
                "failed": update.get("strategiesFailed"),
                "in_databank": update.get("strategies"),
                "strategies_per_hour": update.get("strategiesPerHour"),
                "running_status": update.get("runningStatus"),
                "last_event": update.get("lastEvent"),
            }
            append_jsonl(journal, latest)
            generated = latest["generated"]
            if latest["running_status"] in {3, 4}:
                latest["reason"] = "SQ_FINISHED"
                latest["control_applied"] = False
                append_jsonl(journal, latest)
                return latest
            if isinstance(generated, int) and generated >= attempt_budget:
                latest["reason"] = "ATTEMPT_BUDGET"
                if allow_control:
                    latest["pause_response"] = http_json(gui_url, "project/pause", {"projectName": project})
                    latest["stop_response"] = http_json(gui_url, "project/stop", {"projectName": project})
                    latest["control_applied"] = True
                else:
                    latest["control_applied"] = False
                append_jsonl(journal, latest)
                return latest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui-url", default="http://127.0.0.1:8080")
    parser.add_argument("--project", required=True)
    parser.add_argument("--attempt-budget", required=True, type=int)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--message-timeout", type=int, default=120)
    parser.add_argument("--action", choices=("start", "resume"), default="start")
    parser.add_argument("--allow-control", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run(
        gui_url=args.gui_url, project=args.project, attempt_budget=args.attempt_budget,
        journal=args.journal, message_timeout=args.message_timeout,
        allow_control=args.allow_control, action=args.action,
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
