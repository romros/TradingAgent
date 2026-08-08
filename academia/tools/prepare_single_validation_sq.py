#!/usr/bin/env python3
"""Prepare one sealed pre-holdout SQ Retester project for a selected artifact."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


def rewrite(files: dict[str, bytes], project_name: str) -> dict[str, bytes]:
    result = dict(files)
    config = ET.fromstring(result["config.xml"])
    config.set("name", project_name)
    result["config.xml"] = ET.tostring(config, encoding="utf-8", xml_declaration=True)

    root = ET.fromstring(result["Retest-Task1.xml"])
    main = root.find(".//Data/Setups/Setup")
    if main is None:
        raise ValueError("missing primary retest setup")
    main.attrib.update({
        "dateFrom": "2022.01.01", "dateTo": "2025.07.31",
        "testPrecision": "4",
    })
    chart = main.find("Chart")
    if chart is None or chart.get("symbol") != "EURUSD_M1_dukas_M1_UTCMinus05":
        raise ValueError("validation template does not use the frozen EURUSD resource")
    chart.set("timeframe", "D1")

    expected = {"NumberOfTrades": "30", "ProfitFactor": "1.10", "DrawdownPct": "15"}
    found = set()
    for condition in root.findall(".//Rankings/Conditions/Condition"):
        column = condition.find(".//Column-Value")
        numeric = condition.find(".//Numeric-Value")
        if column is not None and numeric is not None and column.get("column") in expected:
            numeric.set("value", expected[column.get("column")])
            condition.set("use", "true")
            found.add(column.get("column"))
    if found != set(expected):
        raise ValueError(f"validation conditions missing: {sorted(set(expected) - found)}")
    result["Retest-Task1.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return result


def prepare(template: Path, candidate: Path, output: Path, project_name: str) -> Path:
    target_dir = output / project_name
    if target_dir.exists():
        raise FileExistsError(f"refusing to overwrite prepared project: {target_dir}")
    with ZipFile(template) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    rendered = rewrite(files, project_name)
    results = target_dir / "databanks" / "Results"
    results.mkdir(parents=True)
    target = target_dir / "project.cfx"
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for name, payload in rendered.items():
            archive.writestr(name, payload)
    shutil.copy2(candidate, results / candidate.name)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    args = parser.parse_args()
    print(prepare(args.template, args.candidate, args.output, args.project_name))


if __name__ == "__main__":
    main()
