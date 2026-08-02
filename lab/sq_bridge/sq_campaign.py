#!/usr/bin/env python3
"""Prepara i inspecciona campanyes petites de StrategyQuant sense tocar l'original."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path


LIMIT_PATTERNS = (
    (re.compile(r"(<MaxStrategies>)\d+(</MaxStrategies>)"), r"\g<1>{limit}\g<2>"),
    (re.compile(r'(passedStrategies=")\d+(")'), r"\g<1>{limit}\g<2>"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(source: Path, output: Path, project_name: str, limit: int) -> dict:
    if limit < 1 or limit > 1000:
        raise ValueError("limit ha d'estar entre 1 i 1000")
    if source.resolve() == output.resolve():
        raise ValueError("source i output han de ser diferents")

    output.parent.mkdir(parents=True, exist_ok=True)
    changed_limits = 0
    members: list[str] = []

    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as dst:
        for info in src.infolist():
            members.append(info.filename)
            payload = src.read(info.filename)
            if info.filename.endswith(".xml"):
                text = payload.decode("utf-8")
                if info.filename == "config.xml":
                    text, count = re.subn(
                        r'(<Project\s+name=")[^"]+("\s+version=)',
                        rf"\g<1>{project_name}\g<2>",
                        text,
                        count=1,
                    )
                    if count != 1:
                        raise ValueError("No s'ha pogut canviar el nom del projecte")
                for pattern, replacement in LIMIT_PATTERNS:
                    text, count = pattern.subn(replacement.format(limit=limit), text)
                    changed_limits += count
                payload = text.encode("utf-8")
            dst.writestr(info, payload)

    if changed_limits < 2:
        output.unlink(missing_ok=True)
        raise ValueError("No s'han trobat els límits esperats al CFX")

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name,
        "strategy_limit": limit,
        "source": str(source),
        "source_sha256": sha256(source),
        "output": str(output),
        "output_sha256": sha256(output),
        "changed_limit_fields": changed_limits,
        "members": members,
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def inspect(cfx: Path) -> dict:
    with zipfile.ZipFile(cfx, "r") as archive:
        config = archive.read("config.xml").decode("utf-8")
        project_match = re.search(r'<Project\s+name="([^"]+)"', config)
        limits: list[int] = []
        for name in archive.namelist():
            if not name.endswith(".xml"):
                continue
            text = archive.read(name).decode("utf-8")
            limits.extend(int(value) for value in re.findall(r"<MaxStrategies>(\d+)</MaxStrategies>", text))
            limits.extend(int(value) for value in re.findall(r'passedStrategies="(\d+)"', text))
    return {
        "path": str(cfx),
        "sha256": sha256(cfx),
        "project_name": project_match.group(1) if project_match else None,
        "strategy_limits": limits,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--name", required=True)
    prepare_parser.add_argument("--limit", type=int, default=20)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("cfx", type=Path)

    args = parser.parse_args()
    result = (
        prepare(args.source, args.output, args.name, args.limit)
        if args.command == "prepare"
        else inspect(args.cfx)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
