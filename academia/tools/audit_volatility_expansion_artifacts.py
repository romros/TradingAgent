#!/usr/bin/env python3
"""Audit that SQX artifacts implement contraction + breakout + ATR risk."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile


CONTRACTION = ("ATRChangesDown", "ATRFalling")
BREAKOUT = ("BBBarClosesAboveUp", "BBBarClosesBelowDown")
RISK = ("ATR", "StopLoss")


def strategy_text(path: Path) -> str:
    with ZipFile(path) as archive:
        members = [name for name in archive.namelist()
                   if name.lower().endswith("strategy_portfolio.xml")]
        if len(members) != 1:
            raise ValueError(f"expected one strategy_Portfolio.xml, found {len(members)}")
        return archive.read(members[0]).decode("utf-8", errors="replace")


def audit(path: Path) -> dict:
    try:
        text = strategy_text(path)
        contraction = [token for token in CONTRACTION if token in text]
        breakout = [token for token in BREAKOUT if token in text]
        risk = [token for token in RISK if token in text]
        errors = []
    except (OSError, BadZipFile, KeyError, ValueError) as exc:
        contraction, breakout, risk = [], [], []
        errors = [str(exc)]
    passed = bool(contraction and breakout and len(risk) == len(RISK) and not errors)
    return {
        "path": str(path), "passed": passed,
        "contraction_tokens": contraction, "breakout_tokens": breakout,
        "risk_tokens": risk, "errors": errors,
    }


def audit_directory(path: Path) -> dict:
    artifacts = [audit(item) for item in sorted(path.glob("*.sqx"))]
    passed = [item for item in artifacts if item["passed"]]
    return {
        "schema_version": 1,
        "directory": str(path),
        "artifacts_checked": len(artifacts),
        "artifacts_passed": len(passed),
        "artifacts_failed": len(artifacts) - len(passed),
        "passed_paths": [item["path"] for item in passed],
        "artifacts": artifacts,
        "interpretation": "Pass proves the frozen semantic contract, not profitability or robustness."
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = audit_directory(args.directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["artifacts_checked"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
