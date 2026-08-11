#!/usr/bin/env python3
"""Compile and run an exact ATR oracle check against SQ's real ChartData API."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


UTILITY = "SQ/Utils/AlquimiaGapSafeATR.java"
HARNESS = "parity/AlquimiaATRParityHarness.java"
RNG_STUB = "parity/stubs/com/strategyquant/lib/random/MersenneTwisterRng.java"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*, source_root: Path, internal_root: Path, oracle: Path,
        output_dir: Path, runner=subprocess.run,
        image: str = "eclipse-temurin:22-jdk") -> dict:
    source_root, internal_root, oracle, output_dir = (
        path.resolve() for path in (source_root, internal_root, oracle, output_dir))
    sources = [source_root / UTILITY, source_root / HARNESS, source_root / RNG_STUB]
    if not all(path.is_file() for path in sources):
        raise ValueError("parity source missing")
    if not (internal_root / "libs/SQTradingLib.jar").is_file() or not oracle.is_file():
        raise ValueError("SQ libraries or oracle missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "docker", "run", "--rm", "--network", "none",
        "--mount", f"type=bind,src={internal_root},dst=/sq/internal,readonly",
        "--mount", f"type=bind,src={source_root},dst=/src,readonly",
        "--mount", f"type=bind,src={oracle},dst=/oracle.txt,readonly",
        "--mount", f"type=bind,src={output_dir},dst=/out",
        image, "sh", "-lc",
        "set -eu; rm -rf /out/classes; mkdir -p /out/classes; "
        "javac --release 22 -cp '/sq/internal/libs/*' -d /out/classes "
        f"/src/{UTILITY} /src/{HARNESS} /src/{RNG_STUB}; "
        "java -cp '/out/classes:/sq/internal/libs/*' "
        "alquimia.parity.AlquimiaATRParityHarness /oracle.txt",
    ]
    completed = runner(command, capture_output=True, text=True, timeout=300, check=False)
    if completed.returncode or "PASS_EXACT_ATR_PARITY" not in completed.stdout:
        raise RuntimeError("exact SQ parity failed: " +
                           (completed.stderr + completed.stdout)[-3000:])
    return {
        "schema_version": 1,
        "decision": "PASS_EXACT_SQ_CHARTDATA_ATR_PARITY",
        "network_used": False,
        "comparison": "DOUBLE_BITS_EXACT",
        "differences": 0,
        "oracle_path": str(oracle),
        "oracle_sha256": _sha(oracle),
        "sq_trading_lib_sha256": _sha(internal_root / "libs/SQTradingLib.jar"),
        "source_sha256": {path.relative_to(source_root).as_posix(): _sha(path) for path in sources},
        "stdout": completed.stdout.strip(),
        "promotion_scope": "atr_calculation_only",
        "strategy_promotion_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--internal-root", required=True, type=Path)
    parser.add_argument("--oracle", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = run(source_root=args.source_root, internal_root=args.internal_root,
                 oracle=args.oracle, output_dir=args.output_dir)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
