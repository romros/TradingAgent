#!/usr/bin/env python3
"""Reproducibly compile the versioned Alquimia SQ custom block bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


INDICATOR_SOURCE_MEMBER = (
    "SQ/Blocks/Indicators/AlquimiaH4GapSafeSMAATR/"
    "AlquimiaH4GapSafeSMAATR.java"
)
SOURCE_MEMBERS = (
    "SQ/Utils/AlquimiaGapSafeATR.java",
    "SQ/Utils/AlquimiaH4Signals.java",
    "SQ/Blocks/Alquimia/AlquimiaH4MomentumAbove.java",
    "SQ/Blocks/Alquimia/AlquimiaH4MomentumBelow.java",
    "SQ/Blocks/Alquimia/AlquimiaH4ChannelAbove.java",
    "SQ/Blocks/Alquimia/AlquimiaH4ChannelBelow.java",
    "SQ/Blocks/Alquimia/AlquimiaH4CompressionChannelAbove.java",
    "SQ/Blocks/Alquimia/AlquimiaH4CompressionChannelBelow.java",
    "SQ/Blocks/BarAndTime/AlquimiaH4WindowIsContinuous.java",
    INDICATOR_SOURCE_MEMBER,
    "SQ/Formulas/SLPT/AlquimiaH4GapSafeSMAATRValue.java",
)
CLASS_MEMBERS = tuple(member.removesuffix(".java") + ".class"
                      for member in SOURCE_MEMBERS)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*, source_root: Path, internal_root: Path, output_dir: Path,
          runner=subprocess.run, image: str = "eclipse-temurin:22-jdk") -> dict:
    source_root, internal_root, output_dir = (path.resolve() for path in
                                              (source_root, internal_root, output_dir))
    sources = [source_root / member for member in SOURCE_MEMBERS]
    libs = internal_root / "libs"
    if not all(source.is_file() for source in sources) or not (libs / "Snippets.jar").is_file():
        raise ValueError("custom source or SQ libraries missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    java_sources = " ".join(f"/src/{member}" for member in SOURCE_MEMBERS)
    command = [
        "docker", "run", "--rm", "--network", "none",
        "--mount", f"type=bind,src={internal_root},dst=/sq/internal,readonly",
        "--mount", f"type=bind,src={source_root},dst=/src,readonly",
        "--mount", f"type=bind,src={output_dir},dst=/out",
        image, "bash", "-lc",
        "set -euo pipefail; rm -rf /out/classes /out/stubs; "
        "mkdir -p /out/classes /out/stubs/com/strategyquant/lib/snippets; "
        "printf 'package com.strategyquant.lib.snippets; public interface ICustomClasses {}\\n' "
        "> /out/stubs/com/strategyquant/lib/snippets/ICustomClasses.java; "
        "javac --release 22 -cp '/sq/internal/libs/*' -d /out/classes "
        "/out/stubs/com/strategyquant/lib/snippets/ICustomClasses.java "
        + java_sources,
    ]
    completed = runner(command, capture_output=True, text=True, timeout=300,
                       check=False)
    if completed.returncode:
        raise RuntimeError("custom block compilation failed: " + completed.stderr[-2000:])
    compiled = [output_dir / "classes" / member for member in CLASS_MEMBERS]
    if not all(path.is_file() for path in compiled):
        raise RuntimeError("compiled custom block missing")
    for path in compiled:
        header = path.read_bytes()[:8]
        if header[:4] != b"\xca\xfe\xba\xbe" or int.from_bytes(header[6:8], "big") != 66:
            raise RuntimeError("custom block is not a Java 22 class")
    bundle = output_dir / "AlquimiaCryptoH4CustomBlocks-v4.jar"
    with zipfile.ZipFile(bundle, "w") as archive:
        for member, path in zip(CLASS_MEMBERS, compiled):
            info = zipfile.ZipInfo(member, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return {
        "schema_version": 1,
        "decision": "PASS_COMPILE_ONLY_NOT_PARITY",
        "production_sq_modified": False,
        "network_used": False,
        "source_sha256": {member: _sha(source_root / member)
                          for member in SOURCE_MEMBERS},
        "sq_snippets_jar_sha256": _sha(libs / "Snippets.jar"),
        "class_major_version": 66,
        "bundle_path": str(bundle),
        "bundle_sha256": _sha(bundle),
        "promotion_authorized": False,
        "remaining_gate": "SQ_RUNTIME_NUMERIC_PARITY_AND_SEGMENTED_BACKTEST",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--internal-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = build(source_root=args.source_root, internal_root=args.internal_root,
                   output_dir=args.output_dir)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
