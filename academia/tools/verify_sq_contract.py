#!/usr/bin/env python3
"""Comprova que configuració i artifacts SQ compleixen el contracte preregistrat."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


TRUE_VALUES = {"1", "true", "yes"}


def _xml_from_zip(path: Path, member: str) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read(member))


def _identity(node: ET.Element) -> str:
    return next(
        (node.get(key) for key in ("key", "name", "type", "id") if node.get(key)),
        node.tag,
    )


def _active_crosschecks(root: ET.Element) -> list[str]:
    active: set[str] = set()

    def visit(node: ET.Element, in_crosschecks: bool = False) -> None:
        scope = in_crosschecks or "crosscheck" in node.tag.lower()
        enabled = next(
            (node.get(key) for key in ("use", "enabled", "active") if node.get(key) is not None),
            None,
        )
        if scope and enabled is not None and enabled.lower() in TRUE_VALUES:
            active.add(_identity(node))
        for child in node:
            visit(child, scope)

    visit(root)
    return sorted(active)


def _config_values(root: ET.Element, key: str) -> list[str]:
    values: list[str] = []
    wanted = key.lower()
    for node in root.iter():
        identities = {node.tag.lower()}
        identities.update(
            value.lower() for attr in ("key", "name", "type", "id")
            if (value := node.get(attr))
        )
        if wanted not in identities:
            continue
        value = node.get("value")
        if value is None and node.text and node.text.strip():
            value = node.text.strip()
        if value is not None:
            values.append(value)
    return values


def _strategy_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith("strategy_portfolio.xml")]
        if not members:
            raise KeyError("strategy_Portfolio.xml")
        return archive.read(members[0]).decode("utf-8", errors="replace")


def verify(
    project: Path,
    artifacts: list[Path],
    required_tokens: list[str],
    expected_crosschecks: list[str] | None,
    required_values: dict[str, str],
) -> dict:
    errors: list[str] = []
    try:
        config = _xml_from_zip(project, "config.xml")
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        return {"passed": False, "errors": [f"projecte il·legible: {exc}"], "project": str(project)}

    active = _active_crosschecks(config)
    expected = sorted(set(expected_crosschecks or []))
    if expected_crosschecks is not None and active != expected:
        errors.append(f"crosschecks actius {active}; esperats {expected}")

    observed_values: dict[str, list[str]] = {}
    for key, expected_value in required_values.items():
        observed_values[key] = _config_values(config, key)
        if expected_value not in observed_values[key]:
            errors.append(
                f"config {key}={observed_values[key] or '<absent>'}; esperat {expected_value!r}"
            )

    artifact_results = []
    for artifact in artifacts:
        missing: list[str]
        try:
            text = _strategy_text(artifact)
            missing = [token for token in required_tokens if token not in text]
        except (OSError, KeyError, zipfile.BadZipFile) as exc:
            missing = list(required_tokens)
            errors.append(f"artifacte il·legible {artifact}: {exc}")
        if missing:
            errors.append(f"{artifact}: falten {missing}")
        artifact_results.append({"path": str(artifact), "missing_tokens": missing})

    return {
        "passed": not errors,
        "project": str(project),
        "active_crosschecks": active,
        "config_values": observed_values,
        "artifacts_checked": len(artifacts),
        "required_strategy_tokens": required_tokens,
        "artifact_results": artifact_results,
        "errors": errors,
        "interpretation": "Passar aquest gate prova equivalència de contracte, no robustesa ni rendibilitat.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("artifacts", type=Path, nargs="*")
    parser.add_argument("--require-token", action="append", default=[])
    parser.add_argument("--expect-crosscheck", action="append", default=[])
    parser.add_argument("--expect-no-crosschecks", action="store_true")
    parser.add_argument("--require-config-value", action="append", default=[], metavar="KEY=VALUE")
    args = parser.parse_args()
    required_values = dict(item.split("=", 1) for item in args.require_config_value)
    result = verify(
        args.project, args.artifacts, args.require_token,
        [] if args.expect_no_crosschecks else (args.expect_crosscheck or None), required_values,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
