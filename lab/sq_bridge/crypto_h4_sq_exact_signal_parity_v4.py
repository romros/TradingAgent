#!/usr/bin/env python3
"""Run exact Python↔SQ parity for combined H4 signal blocks."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


SOURCES = ("SQ/Utils/AlquimiaGapSafeATR.java", "SQ/Utils/AlquimiaH4Signals.java",
           "parity/AlquimiaSignalParityHarness.java",
           "parity/stubs/com/strategyquant/lib/random/MersenneTwisterRng.java")


def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*, source_root: Path, internal_root: Path, price_oracle: Path,
        signal_oracle: Path, output_dir: Path, runner=subprocess.run,
        image: str = "eclipse-temurin:22-jdk") -> dict:
    source_root, internal_root, price_oracle, signal_oracle, output_dir = (
        path.resolve() for path in
        (source_root, internal_root, price_oracle, signal_oracle, output_dir))
    sources = [source_root / member for member in SOURCES]
    if not all(path.is_file() for path in sources) or not all(
            path.is_file() for path in (price_oracle, signal_oracle,
                                        internal_root / "libs/SQTradingLib.jar")):
        raise ValueError("signal parity input missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    java_sources = " ".join(f"/src/{member}" for member in SOURCES)
    command = ["docker", "run", "--rm", "--network", "none",
        "--mount", f"type=bind,src={internal_root},dst=/sq/internal,readonly",
        "--mount", f"type=bind,src={source_root},dst=/src,readonly",
        "--mount", f"type=bind,src={price_oracle},dst=/prices.txt,readonly",
        "--mount", f"type=bind,src={signal_oracle},dst=/signals.txt,readonly",
        "--mount", f"type=bind,src={output_dir},dst=/out", image, "sh", "-lc",
        "set -eu; rm -rf /out/classes; mkdir -p /out/classes; "
        f"javac --release 22 -cp '/sq/internal/libs/*' -d /out/classes {java_sources}; "
        "java -cp '/out/classes:/sq/internal/libs/*' "
        "alquimia.parity.AlquimiaSignalParityHarness /prices.txt /signals.txt"]
    completed = runner(command, capture_output=True, text=True, timeout=300, check=False)
    if completed.returncode or "PASS_EXACT_SIGNAL_PARITY" not in completed.stdout:
        raise RuntimeError("exact SQ signal parity failed: " +
                           (completed.stderr + completed.stdout)[-3000:])
    return {"schema_version": 1, "decision": "PASS_EXACT_SQ_CHARTDATA_SIGNAL_PARITY",
            "network_used": False, "differences": 0,
            "price_oracle_sha256": _sha(price_oracle),
            "signal_oracle_sha256": _sha(signal_oracle),
            "source_sha256": {path.relative_to(source_root).as_posix(): _sha(path)
                              for path in sources},
            "sq_trading_lib_sha256": _sha(internal_root / "libs/SQTradingLib.jar"),
            "stdout": completed.stdout.strip(),
            "promotion_scope": "combined_signal_calculation_only",
            "strategy_promotion_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--internal-root", required=True, type=Path)
    parser.add_argument("--price-oracle", required=True, type=Path)
    parser.add_argument("--signal-oracle", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = run(source_root=args.source_root, internal_root=args.internal_root,
                 price_oracle=args.price_oracle, signal_oracle=args.signal_oracle,
                 output_dir=args.output_dir)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__": main()
