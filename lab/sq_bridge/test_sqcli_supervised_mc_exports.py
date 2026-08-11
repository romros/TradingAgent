import json
import re
import zipfile
from pathlib import Path

import pytest

from lab.sq_bridge.sqcli_supervised_mc_exports import (
    export_all, verify_export_receipt,
)
from lab.sq_bridge.sqx_monte_carlo_materialize import materialize
from lab.sq_bridge.test_sqx_monte_carlo_contract import _sqx


HEADER = ('"Ticket";"Type";"Open time";"Open price";"Close time";'
          '"Close price";"Size";"Profit/Loss";"MAE ($)"\n')


def _materialization(root: Path, count: int = 4) -> Path:
    source = _sqx(root, count=count)
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr("settings.xml", "settings")
        archive.writestr("strategy_Portfolio.xml", "strategy")
        archive.writestr("version.txt", "3")
    directory = root / "project" / "materialized"
    materialize(source, directory, simulations=count,
                probability_pct=10, max_change_pct=10)
    return directory / "materialization.manifest.json"


def _exporter(host_root: Path, calls: list[str], fail_after: int | None = None):
    def export(command: str) -> str:
        if fail_after is not None and len(calls) >= fail_after:
            raise RuntimeError("simulated interruption")
        calls.append(command)
        match = re.search(r" output=(\S+) usecomma", command)
        assert match
        relative = Path(match.group(1)).relative_to("/sq-projects")
        target = host_root / relative
        Path(str(target) + ".csv").write_text(
            HEADER + ('"1";"Buy";"2020.01.01 00:00:00";"1";'
                      '"2020.01.02 00:00:00";"1.01";"100";"1";"-2"\n'))
        return "ok"
    return export


def test_exports_all_native_runs_and_verifies_every_csv(tmp_path):
    manifest = _materialization(tmp_path)
    calls, progress = [], []
    receipt = export_all(
        materialization_manifest=manifest,
        output_dir=tmp_path / "project" / "exports",
        host_projects_root=tmp_path,
        container_projects_root="/sq-projects",
        export_fn=_exporter(tmp_path, calls), progress_hook=progress.append)
    assert receipt["completed_count"] == 4
    assert len(calls) == 4
    assert [row["completed"] for row in progress] == [1, 2, 3, 4]
    assert verify_export_receipt(
        tmp_path / "project" / "exports" / "supervised-mc-exports.receipt.json") == receipt


def test_resumes_after_interruption_without_reexporting_completed_runs(tmp_path):
    manifest = _materialization(tmp_path)
    output = tmp_path / "project" / "exports"
    calls = []
    with pytest.raises(RuntimeError, match="interruption"):
        export_all(materialization_manifest=manifest, output_dir=output,
                   host_projects_root=tmp_path,
                   container_projects_root="/sq-projects",
                   export_fn=_exporter(tmp_path, calls, fail_after=2))
    assert len(list((output / "checkpoints").glob("*.json"))) == 2
    resumed_calls, progress = [], []
    receipt = export_all(
        materialization_manifest=manifest, output_dir=output,
        host_projects_root=tmp_path, container_projects_root="/sq-projects",
        export_fn=_exporter(tmp_path, resumed_calls), progress_hook=progress.append)
    assert receipt["completed_count"] == 4
    assert len(resumed_calls) == 2
    assert [row["event"] for row in progress] == [
        "reused", "reused", "exported", "exported"]


def test_receipt_detects_csv_tampering_and_paths_outside_mount(tmp_path):
    manifest = _materialization(tmp_path)
    output = tmp_path / "project" / "exports"
    receipt = export_all(
        materialization_manifest=manifest, output_dir=output,
        host_projects_root=tmp_path, container_projects_root="/sq-projects",
        export_fn=_exporter(tmp_path, []))
    Path(receipt["runs"][0]["orders_csv_path"]).write_text(HEADER)
    with pytest.raises(ValueError, match="LINEAGE"):
        verify_export_receipt(output / "supervised-mc-exports.receipt.json")

    with pytest.raises(ValueError, match="OUTSIDE"):
        export_all(materialization_manifest=manifest,
                   output_dir=tmp_path.parent / "outside-mc-export-test",
                   host_projects_root=tmp_path,
                   container_projects_root="/sq-projects",
                   export_fn=lambda _: "unused")
