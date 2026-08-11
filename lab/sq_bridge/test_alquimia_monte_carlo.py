#!/usr/bin/env python3
import zipfile
from pathlib import Path

import pytest

from alquimia_monte_carlo import generate, verify


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


assert callable(generate)
