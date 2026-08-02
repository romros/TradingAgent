#!/usr/bin/env python3
"""Inventaria capacitats SQ configurades i artifacts executats, sempre en lectura."""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


MEMBER_MARKERS = {
    "higher_precision": "higherprecision",
    "monte_carlo": "monte",
    "walk_forward": "results/wf:",
    "additional_market": "additionalmarket",
}


def audit(root: Path) -> dict:
    task_types: Counter[str] = Counter()
    unreadable_projects = 0
    for project in root.glob("*/project.cfx"):
        try:
            with zipfile.ZipFile(project) as archive:
                config = ET.fromstring(archive.read("config.xml"))
        except (KeyError, OSError, zipfile.BadZipFile, ET.ParseError):
            unreadable_projects += 1
            continue
        task_types.update(node.get("type", "unknown") for node in config.findall(".//Task"))

    artifact_markers: Counter[str] = Counter()
    sqx_total = 0
    unreadable_sqx = 0
    for artifact in root.rglob("*.sqx"):
        sqx_total += 1
        try:
            with zipfile.ZipFile(artifact) as archive:
                names = [name.lower() for name in archive.namelist()]
        except (OSError, zipfile.BadZipFile):
            unreadable_sqx += 1
            continue
        for label, marker in MEMBER_MARKERS.items():
            artifact_markers[label] += sum(marker in name for name in names)

    return {
        "root": str(root),
        "configured_task_types": dict(sorted(task_types.items())),
        "sqx_artifacts": sqx_total,
        "executed_result_members": dict(sorted(artifact_markers.items())),
        "unreadable": {"projects": unreadable_projects, "sqx": unreadable_sqx},
        "interpretation": "Una tasca configurada no equival a un resultat executat.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
