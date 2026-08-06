import json

import pytest

from run_sq_gui_pilot import engine_update, project_preflight


def test_preflight_rejects_unresolved_project():
    response = {"projects": [{"projectName": "P", "tasks": 1, "hasUnresolvedResources": True}]}
    with pytest.raises(ValueError, match="unresolved"):
        project_preflight(response, "P")


def test_preflight_requires_one_task():
    response = {"projects": [{"projectName": "P", "tasks": 2, "hasUnresolvedResources": False}]}
    with pytest.raises(ValueError, match="exactly one task"):
        project_preflight(response, "P")


def test_extracts_real_attempt_counter_from_engine_channel():
    message = json.dumps({
        "projectData": {"name": "P", "channels": [
            {"name": "engine-channel", "data": {"totalJobsDone": 123, "strategies": 4}}
        ]}
    })
    assert engine_update(message, "P") == {"totalJobsDone": 123, "strategies": 4}
    assert engine_update(message, "OTHER") is None
