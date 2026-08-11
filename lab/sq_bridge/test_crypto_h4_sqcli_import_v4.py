import shutil
import subprocess
from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_sqcli_import_v4 import import_batch
from lab.sq_bridge.test_crypto_h4_project_batch_v4 import (
    SCAFFOLD, _compile, _selector,
)


def _runtime(batch, *, unresolved=False, running=False):
    current = []
    source = Path(next(iter(batch["projects"].values()))["cfx_path"])

    def list_fn(_base_url):
        if running:
            return [{"projectName": "OTHER", "runningStatus": 1,
                     "hasUnresolvedResources": False}]
        return list(current)

    def open_fn(_base_url, _temporary):
        name = next(iter(batch["projects"].values()))["project_name"]
        current.append({"projectName": name, "runningStatus": 0,
                        "hasUnresolvedResources": unresolved})
        return {"success": "loaded", "projectName": name}

    calls = []

    def runner(command, **_kwargs):
        calls.append(command)
        if command[:2] == ["docker", "cp"] and command[2].startswith("sqcli-docker:"):
            destination = Path(command[3]); destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        return subprocess.CompletedProcess(command, 0, "", "")

    return list_fn, open_fn, runner, calls


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_imports_verified_batch_without_starting_sqcli(tmp_path):
    batch = _compile(_selector(tmp_path), tmp_path / "batch")
    list_fn, open_fn, runner, calls = _runtime(batch)
    receipt = import_batch(
        batch_path=tmp_path / "batch/crypto_h4_project_batch.json",
        output_dir=tmp_path / "import", list_fn=list_fn, open_fn=open_fn,
        runner=runner)
    assert receipt["decision"] == "PASS_CRYPTO_SQCLI_IMPORT"
    assert receipt["sqcli_started"] is False
    assert receipt["python_parity_required"] is True
    assert receipt["strategy_promotion_authorized"] is False
    assert all("start" not in " ".join(command).lower() for command in calls)


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_refuses_import_while_any_sq_project_runs(tmp_path):
    batch = _compile(_selector(tmp_path), tmp_path / "batch")
    list_fn, open_fn, runner, _ = _runtime(batch, running=True)
    with pytest.raises(RuntimeError, match="projects run"):
        import_batch(batch_path=tmp_path / "batch/crypto_h4_project_batch.json",
            output_dir=tmp_path / "import", list_fn=list_fn,
            open_fn=open_fn, runner=runner)


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_rejects_sqcli_resource_resolution_failure(tmp_path):
    batch = _compile(_selector(tmp_path), tmp_path / "batch")
    list_fn, open_fn, runner, _ = _runtime(batch, unresolved=True)
    with pytest.raises(RuntimeError, match="unresolved"):
        import_batch(batch_path=tmp_path / "batch/crypto_h4_project_batch.json",
            output_dir=tmp_path / "import", list_fn=list_fn,
            open_fn=open_fn, runner=runner)
