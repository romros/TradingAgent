#!/usr/bin/env python3
"""Prepare disposable SQ projects for the final local capability tests."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


EXPECTED_CANDIDATE = "3470b786bd4416d44a7a5be9d93dd39d2fdc52cf39681123b75443395f5e2ca2"


def rewrite_cfx(
    source: Path,
    target: Path,
    project_name: str,
    replacements: dict[str, dict[str, str]],
) -> None:
    with ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    config = files["config.xml"].decode("utf-8")
    old_name = config.split('name="', 1)[1].split('"', 1)[0]
    files["config.xml"] = config.replace(f'name="{old_name}"', f'name="{project_name}"', 1).encode()
    for name, changes in replacements.items():
        payload = files[name]
        text = payload.decode("utf-8").replace("\r\n", "\n")
        for old, new in changes.items():
            if old not in text:
                raise ValueError(f"missing expected fragment in {source}: {old}")
            text = text.replace(old, new)
        files[name] = text.encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)


def prepare_builder(projects: Path, source_name: str, target_name: str, mode: str) -> None:
    source = projects / source_name / "project.cfx"
    target_dir = projects / target_name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    generation = "random-generation" if mode == "random" else "genetic-evolution"
    rewrite_cfx(
        source,
        target_dir / "project.cfx",
        target_name,
        {
            "config.xml": {
                '    <Task type="Build" name="Build" showSettingsOverview="false" sampleName="Custom" active="true" version="126.2189" taskXMLFile="Build-Task1.xml" />\n'
                '    <Task name="Filter strategies" type="Filtering" taskXMLFile="Filtering-Task1.xml" active="true" />\n'
                '    <Task type="Retest" name="Retest strategies" showSettingsOverview="false" sampleName="Custom" active="true" taskXMLFile="Retest-Task1.xml" />\n'
                '    <Task name="Clear databanks" type="ClearDatabanks" taskXMLFile="ClearDatabanks-Task1.xml" active="true" />\n'
                '    <Task name="Go To Task" type="GoToTask" taskXMLFile="GoToTask-Task1.xml" active="true" />':
                    '    <Task type="Build" name="Build" showSettingsOverview="false" sampleName="Custom" active="true" version="126.2189" taskXMLFile="Build-Task1.xml" />',
            },
            "Build-Task1.xml": {
            '<BuildMode generationType="genetic-evolution">': f'<BuildMode generationType="{generation}">',
            "<PopulationSize>100</PopulationSize>": "<PopulationSize>100</PopulationSize>",
            "<MaxGenerations>100</MaxGenerations>": "<MaxGenerations>1</MaxGenerations>",
            '<StopCondition type="databank-full" passedStrategies="300" restartCount="5" days="0" hours="1" minutes="0" />':
                '<StopCondition type="finished-evolution" passedStrategies="2000" restartCount="0" days="0" hours="0" minutes="20" />',
            '<CrossChecks use="true" evaluateAll="true">': '<CrossChecks use="false" evaluateAll="true">',
            'testPrecision="1"': 'testPrecision="4"',
            'timeframe="M15"': 'timeframe="H4"',
            },
        },
    )


def prepare_mc(projects: Path, source_name: str, target_name: str) -> None:
    source_dir = projects / source_name
    target_dir = projects / target_name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)
    rewrite_cfx(
        source_dir / "project.cfx",
        target_dir / "project.cfx",
        target_name,
        {
            "config.xml": {
                '<Databank name="Validation" view="Default - Main data" syncType="Auto-sync never" position="1" />':
                    '<Databank name="Validation" view="Default - Main data" syncType="Auto-sync never" position="1" />'
                    '<Databank name="Existing portfolio" view="Default - Main data" syncType="Auto-sync never" position="2" />',
            },
            "Retest-Task1.xml": {
            '<CrossChecks use="false" evaluateAll="true">': '<CrossChecks use="true" evaluateAll="true">',
            '<MonteCarloRetest use="false">': '<MonteCarloRetest use="true">',
            "<NumberOfSimulations>10</NumberOfSimulations>": "<NumberOfSimulations>50</NumberOfSimulations>",
            '<Method use="true" type="RandomizeHistoryData">': '<Method use="false" type="RandomizeHistoryData">',
            '<Method use="true" type="RandomizeMinDistance">': '<Method use="false" type="RandomizeMinDistance">',
            '<Method use="true" type="RandomizeSlippage">': '<Method use="false" type="RandomizeSlippage">',
            '<Method use="true" type="RandomizeSpread">': '<Method use="false" type="RandomizeSpread">',
            '<Method use="true" type="RandomizeStartingBar">': '<Method use="false" type="RandomizeStartingBar">',
            '<DeleteFailedStrategies>true</DeleteFailedStrategies>': '<DeleteFailedStrategies>false</DeleteFailedStrategies>',
            '<FitPortfolio active="false" databank="Existing portfolio">': '<FitPortfolio active="false" databank="Results">',
            '<Method type="PerTrade" use="true">\n                <Params>\n                  <Param key="Commission" className="PerTrade">0.4</Param>\n                </Params>\n              </Method>\n              <Method type="None" use="true">':
                '<Method type="PerTrade" use="true">\n                <Params>\n                  <Param key="Commission" className="PerTrade">0.4</Param>\n                </Params>\n              </Method>\n              <Method type="None" use="false">',
            },
        },
    )
    candidate = source_dir / "databanks" / "Validation" / "Strategy 4.1.133.sqx"
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if digest != EXPECTED_CANDIDATE:
        raise ValueError(f"candidate hash mismatch: {digest}")
    results = target_dir / "databanks" / "Results"
    results.mkdir(parents=True)
    shutil.copy2(candidate, results / candidate.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime", type=Path)
    args = parser.parse_args()
    projects = args.runtime / "user" / "projects"
    prepare_builder(projects, "EURUSD", "ACADEMIA_BUILDER_RANDOM", "random")
    prepare_builder(projects, "EURUSD", "ACADEMIA_BUILDER_GENETIC", "genetic")
    prepare_mc(projects, "ALQUIMIA_EURUSD_H4_VALIDATION_RISK1", "ACADEMIA_MC_PARAMETERS")
    print("prepared ACADEMIA_BUILDER_RANDOM, ACADEMIA_BUILDER_GENETIC, ACADEMIA_MC_PARAMETERS")


if __name__ == "__main__":
    main()
