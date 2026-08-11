import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.alquimia_monte_carlo import generate as generate_mc
from lab.sq_bridge.sqcli_supervised_monte_carlo import (
    supervised_monte_carlo, verify_monte_carlo_receipt,
)
from lab.sq_bridge.test_alquimia_retest import _generate as generate_retest
from lab.sq_bridge.sqx_monte_carlo_materialize import materialize, verify_manifest


LOG = """Project: MC_T
TASK STARTED
Databanks before start: Results (1), PreHoldout (0)
TASK FINISHED at 2026.08.11 02:00:00 in 2 s.
Databanks after finish: Results (1), PreHoldout (1)
Total tested: 1, Time per strategy: 0 ms., Passed: 1, Failed: 0
"""


def _mc_project(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _, source = generate_retest(source_dir)
    base_manifest_path = source.with_suffix(".manifest.json")
    with zipfile.ZipFile(source) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    task = ET.fromstring(members["Retest-Task1.xml"])
    crosschecks = task.find("./CrossChecks")
    ET.SubElement(crosschecks, "MonteCarloManipulation", {"use": "false"})
    mc = ET.SubElement(crosschecks, "MonteCarloRetest", {"use": "false"})
    settings = ET.SubElement(mc, "Settings")
    methods = ET.SubElement(settings, "Methods")
    method = ET.SubElement(methods, "Method", {
        "type": "RandomizeStrategyParameters", "use": "false"})
    params = ET.SubElement(method, "Params")
    for key, value in (("Probability", "10"), ("MaxChange", "10"),
                       ("Symmetric", "true")):
        ET.SubElement(params, "Param", {"key": key}).text = value
    ET.SubElement(settings, "NumberOfSimulations").text = "50"
    members["Retest-Task1.xml"] = ET.tostring(task, encoding="utf-8")
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    base = json.loads(base_manifest_path.read_text())
    base["cfx_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    base_manifest_path.write_text(json.dumps(base))
    cfx = tmp_path / "mc.cfx"
    manifest = generate_mc(
        source, cfx, "MC_T", 1000,
        base_retest_manifest_path=base_manifest_path)
    return manifest, cfx, cfx.with_suffix(".manifest.json")


def test_supervises_native_monte_carlo_and_replays_verified_receipt(tmp_path):
    manifest, cfx, manifest_path = _mc_project(tmp_path)
    projects_root = tmp_path / "projects"
    project_dir = projects_root / "MC_T"
    state = {"imported": False, "started": False, "synced": False, "poll": 0}

    def listing(_base_url):
        if not state["imported"]:
            return []
        running = 0
        if state["started"]:
            state["poll"] += 1
            running = 1 if state["poll"] == 1 else 0
        return [{"projectName": "MC_T", "runningStatus": running,
                 "hasUnresolvedResources": False,
                 "strategies": 1 if state["synced"] else 0}]

    def open_project(_base_url, _container_path):
        project_dir.mkdir(parents=True)
        shutil.copyfile(cfx, project_dir / "project.cfx")
        state["imported"] = True
        return {"success": "ok", "projectName": "MC_T"}

    def start_project(_base_url, _project):
        source_sqx = next((project_dir / "databanks/Results").glob("*.sqx"))
        target = project_dir / "databanks/PreHoldout" / source_sqx.name
        result_xml = """<RobustnessResults><NumberOfSimulations>1000</NumberOfSimulations>
          <Symbol>NVDA</Symbol><TimeFrame>M15</TimeFrame>
          <DateRange>2017.01.01 - 2025.07.31</DateRange><Methods><Method>
          Randomize strategy parameters, with probability 10 % and max change 10 %
          </Method></Methods></RobustnessResults>"""
        with zipfile.ZipFile(source_sqx) as source, zipfile.ZipFile(target, "w") as output:
            for name in source.namelist():
                output.writestr(name, source.read(name))
            prefix = "Results/Main: NVDA/M15"
            output.writestr(f"{prefix}/MonteCarloRetest_Results.xml", result_xml)
            for index in range(1000):
                output.writestr(
                    f"{prefix}/MonteCarloRetest_Simulation{index}Orders.bin",
                    f"orders-{index}")
            output.writestr("orders.bin", b"main-orders")
        state["started"] = True
        return {"success": "started"}

    def sync(command):
        if "syncfromfiles" in command:
            state["synced"] = True
        return "synced"

    def export(command):
        output_sqx = next((project_dir / "databanks/PreHoldout").glob("*.sqx"))
        token = hashlib.sha256(output_sqx.read_bytes()).hexdigest()[:16]
        (project_dir / f"orders-pre-holdout-{token}.csv").write_text(
            '"Ticket";"Type";"Open time";"Open price";"Close time";"Close price"\n')
        return "exported"

    def runner(args, **_kwargs):
        return subprocess.CompletedProcess(args, 0, "", "")

    output_dir = tmp_path / "evidence"
    result = supervised_monte_carlo(
        cfx_path=cfx, manifest_path=manifest_path, output_dir=output_dir,
        projects_root=projects_root, listing_fn=listing, open_fn=open_project,
        start_fn=start_project,
        final_log_fn=lambda _project: {
            "log_text": LOG, "completion_source": "sq_project_final_log"},
        sync_fn=sync, export_fn=export, runner=runner,
        sleep_fn=lambda _seconds: None, interval=1, timeout_seconds=10)
    assert result["decision"] == "PASS_SUPERVISED_MONTE_CARLO"
    receipt = output_dir / "supervised_monte_carlo_receipt.json"
    assert verify_monte_carlo_receipt(receipt) == result
    materialized_dir = project_dir / "materialized"
    materialized = materialize(
        Path(result["retest_output_sqx_path"]), materialized_dir,
        simulations=1000, probability_pct=10, max_change_pct=10,
        supervised_mc_receipt=receipt)
    assert materialized["evidence_class"] == "observed"
    assert verify_manifest(
        materialized_dir / "materialization.manifest.json") == materialized
    replay = supervised_monte_carlo(
        cfx_path=cfx, manifest_path=manifest_path, output_dir=output_dir,
        projects_root=projects_root,
        listing_fn=lambda *_: (_ for _ in ()).throw(AssertionError("must replay")))
    assert replay == result
