#!/usr/bin/env python3
import zipfile
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from alquimia_monte_carlo import generate, verify, verify_project
from lab.sq_bridge.test_alquimia_retest import _generate as generate_retest


def _source(path: Path) -> Path:
    source = path / "source.cfx"
    config = b'''<Config name="OLD"><Tasks><Task type="Retest" taskXMLFile="Retest-Task1.xml"/></Tasks></Config>'''
    task = b'''<Settings><CrossChecks use="false" evaluateAll="false">
      <MonteCarloManipulation use="true"/>
      <MonteCarloRetest use="false"><Settings><Methods>
        <Method type="RandomizeStrategyParameters" use="false"><Params>
          <Param key="Probability">20</Param><Param key="MaxChange">20</Param>
          <Param key="Symmetric">false</Param></Params></Method>
        <Method type="RandomizeHistoryData" use="true"><Params/></Method>
      </Methods><NumberOfSimulations>50</NumberOfSimulations></Settings></MonteCarloRetest>
    </CrossChecks><Rankings><DeleteFailedStrategies>true</DeleteFailedStrategies></Rankings></Settings>'''
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("config.xml", config)
        archive.writestr("Retest-Task1.xml", task)
    return source


def test_monte_carlo_cfx_is_active_exclusive_verified_and_reproducible(tmp_path):
    source = _source(tmp_path)
    first, second = tmp_path / "first.cfx", tmp_path / "second.cfx"
    one = generate(source, first, "MC_T", 1000, 10, 10)
    two = generate(source, second, "MC_T", 1000, 10, 10)
    assert first.read_bytes() == second.read_bytes()
    assert one == two
    assert verify(first, one, source=source)["simulations"] == 1000
    with zipfile.ZipFile(first) as archive:
        task = archive.read("Retest-Task1.xml")
    assert b'MonteCarloRetest use="true"' in task
    assert b'MonteCarloManipulation use="false"' in task


def test_monte_carlo_verifier_detects_summary_tampering(tmp_path):
    source = _source(tmp_path)
    output = tmp_path / "out.cfx"
    manifest = generate(source, output, "MC_T", 1000)
    with pytest.raises(ValueError, match="CONTRACT"):
        verify(output, dict(manifest, simulations=999), source=source)


def test_monte_carlo_project_binds_pre_holdout_candidate_lineage(tmp_path):
    base, source = generate_retest(tmp_path)
    base_manifest = source.with_suffix(".manifest.json")
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
    base = json.loads(base_manifest.read_text())
    base["cfx_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    base_manifest.write_text(json.dumps(base))
    output = tmp_path / "mc.cfx"
    manifest = generate(
        source, output, "MC_T", 1000,
        base_retest_manifest_path=base_manifest)
    assert manifest["candidate_id"] == "T"
    assert verify_project(output, manifest)["candidate_id"] == "T"
    with pytest.raises(ValueError, match="CANDIDATE"):
        verify_project(output, dict(manifest, candidate_id="other"))


assert callable(generate)
