#!/usr/bin/env python3
"""Converteix una extracció curta en una observació traçable de campanya.

L'extracció conté només mètriques i conclusions transformadores. Els artifacts
originals es llegeixen per calcular-ne el hash, però no es copien.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DECISIONS = {"CONTINUE", "DIRECTED_TEST", "REJECT"}
EVIDENCE_STATUS = {"tested", "verified"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(draft: dict, repository_root: Path) -> dict:
    required = {"campaign_id", "family", "source_artifacts", "observations", "assessment"}
    missing = sorted(required - draft.keys())
    if missing:
        raise ValueError(f"falten camps: {', '.join(missing)}")

    assessment = draft["assessment"]
    if assessment.get("decision") not in DECISIONS:
        raise ValueError("decisió no admesa")
    if assessment.get("evidence_status") not in EVIDENCE_STATUS:
        raise ValueError("estat d'evidència no admès")
    for field in ("insight_code", "reason", "next_test"):
        if not assessment.get(field):
            raise ValueError(f"assessment.{field} és obligatori")

    artifacts = []
    for source in draft["source_artifacts"]:
        relative = Path(source["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("els artifacts han de ser paths relatius al repositori")
        artifact = repository_root / relative
        if not artifact.is_file():
            raise ValueError(f"artifact inexistent: {relative}")
        artifacts.append({"path": relative.as_posix(), "sha256": sha256(artifact), "role": source["role"]})

    return {
        "schema_version": 1,
        "campaign_id": draft["campaign_id"],
        "family": draft["family"],
        "source_artifacts": artifacts,
        "observations": draft["observations"],
        "assessment": assessment,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="extracció JSON curta")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    draft = json.loads(args.input.read_text(encoding="utf-8"))
    result = normalize(draft, args.repository_root)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
