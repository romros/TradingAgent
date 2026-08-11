#!/usr/bin/env python3
"""Build an isolated, source-hashed SQ Signal logger jar with JDK 22."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


SUPPORTED_SIGNAL_SOURCE_SHA256 = {
    "43b75f4a4e244f393123f66950b57cd58cb979a4483ded18237d0c3e92ddd68e",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instrument(source: str) -> str:
    """Patch exact stable anchors; fail if the installed SQ source changed."""
    replacements = [
        ("import java.util.ArrayList;\nimport java.util.List;",
         "import java.util.ArrayList;\nimport java.util.List;\n"
         "import java.io.BufferedWriter;\nimport java.io.File;\n"
         "import java.io.FileWriter;\nimport java.io.IOException;\n"
         "import java.io.PrintWriter;\nimport java.nio.charset.StandardCharsets;"),
        ("import com.strategyquant.lib.SQTime;\n", ""),
        ("private Variable[] signalVariables = null;",
         "private Variable[] signalVariables = null;\n"
         "\tprivate String[] signalVariableIds = null;\n"
         "\tprivate PrintWriter alquimiaSignalWriter = null;"),
        ("\t\t\tvar.setValue(value);",
         "\t\t\tvar.setValue(value);\n"
         "\t\t\tif(updateEventType == barEventType) {\n"
         "\t\t\t\twriteAlquimiaSignal(signalVariableIds[i], value);\n"
         "\t\t\t}"),
        ("\t\tArrayList<Variable> alSignalVariables = new ArrayList<Variable>();",
         "\t\tArrayList<Variable> alSignalVariables = new ArrayList<Variable>();\n"
         "\t\tArrayList<String> alSignalVariableIds = new ArrayList<String>();"),
        ("parseSignal(elSignal, alSignals, alSignalVariables);",
         "parseSignal(elSignal, alSignals, alSignalVariables, alSignalVariableIds);"),
        ("\t\t\tsignalVariables = new Variable[alSignals.size()];",
         "\t\t\tsignalVariables = new Variable[alSignals.size()];\n"
         "\t\t\tsignalVariableIds = new String[alSignals.size()];"),
        ("\t\t\t\tsignalVariables[i] = alSignalVariables.get(i);",
         "\t\t\t\tsignalVariables[i] = alSignalVariables.get(i);\n"
         "\t\t\t\tsignalVariableIds[i] = alSignalVariableIds.get(i);"),
        ("\t\talSignalVariables.clear();",
         "\t\talSignalVariables.clear();\n\t\talSignalVariableIds.clear();"),
        ("private void parseSignal(Element elSignal, ArrayList<IBlock> signals, ArrayList<Variable> signalVariables)",
         "private void parseSignal(Element elSignal, ArrayList<IBlock> signals, ArrayList<Variable> signalVariables, ArrayList<String> signalVariableIds)"),
        ("\t\t\tsignalVariables.add(signalVar);\n\t\t\tsignals.add(falseBool);",
         "\t\t\tsignalVariables.add(signalVar);\n"
         "\t\t\tsignalVariableIds.add(signalVarId);\n"
         "\t\t\tsignals.add(falseBool);"),
        ("\t\tsignalVariables.add(signalVar);\n\t\tsignals.add(block);",
         "\t\tsignalVariables.add(signalVar);\n"
         "\t\tsignalVariableIds.add(signalVarId);\n"
         "\t\tsignals.add(block);"),
    ]
    result = source
    for old, new in replacements:
        if result.count(old) != 1:
            raise ValueError(f"SQ Signal.java anchor mismatch: {old[:60]!r}")
        result = result.replace(old, new)
    marker = "\n\t//------------------------------------------------------------------------\n\n\t@Override\n\tprotected void parseXml"
    method = r'''
	// Alquimia parity probe: enabled only in the isolated process via env.
	private void writeAlquimiaSignal(String variableId, boolean value) throws TradingException {
		String path = System.getenv("ALQUIMIA_SIGNAL_LOG_PATH");
		if(path == null || path.length() == 0) return;
		try {
			if(alquimiaSignalWriter == null) {
				File output = new File(path);
				File parent = output.getParentFile();
				if(parent != null) parent.mkdirs();
				alquimiaSignalWriter = new PrintWriter(new BufferedWriter(
					new FileWriter(output, StandardCharsets.UTF_8, true)));
			}
			long strategyTime = Strategy.Time(0);
			alquimiaSignalWriter.println(strategyTime+";"+variableId+";"+(value ? "1" : "0"));
			alquimiaSignalWriter.flush();
		} catch(IOException e) {
			throw new TradingException(e);
		}
	}

	@Override
	public void deinitialize() {
		if(alquimiaSignalWriter != null) {
			alquimiaSignalWriter.close();
			alquimiaSignalWriter = null;
		}
		super.deinitialize();
	}
'''
    if result.count(marker) != 1:
        raise ValueError("SQ Signal.java method insertion anchor mismatch")
    return result.replace(marker, method + marker)


def _replace_class_deterministically(*, original_jar: Path, class_file: Path,
                                     output_jar: Path) -> None:
    """Rewrite one class while preserving all other ZIP metadata and ordering."""
    member = "SQ/Internal/RulesImpl/Signal.class"
    temporary = output_jar.with_suffix(output_jar.suffix + ".tmp")
    replacement = class_file.read_bytes()
    found = 0
    with zipfile.ZipFile(original_jar, "r") as source, zipfile.ZipFile(
            temporary, "w", allowZip64=True) as target:
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == member:
                found += 1
                payload = replacement
            target.writestr(info, payload)
    if found != 1:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"expected exactly one {member} in Snippets.jar, got {found}")
    temporary.replace(output_jar)


def build(*, internal_root: Path, output_dir: Path,
          builder_image: str = "eclipse-temurin:22-jdk",
          runner=subprocess.run) -> dict:
    source = internal_root / "extend/Snippets/SQ/Internal/RulesImpl/Signal.java"
    original_jar = internal_root / "libs/Snippets.jar"
    if not source.is_file() or not original_jar.is_file():
        raise ValueError("SQ Signal source or Snippets.jar missing")
    source_hash = _sha(source)
    if source_hash not in SUPPORTED_SIGNAL_SOURCE_SHA256:
        raise ValueError("unsupported SQ Signal.java version")
    patched = instrument(source.read_text())
    output_dir = output_dir.resolve()
    java = output_dir / "src/SQ/Internal/RulesImpl/Signal.java"
    java.parent.mkdir(parents=True, exist_ok=True)
    java.write_text(patched)
    # Compile-only compatibility type. SQ supplies the real proprietary type at
    # runtime; this stub is deliberately excluded from the output JAR.
    stub = output_dir / "src/com/strategyquant/lib/snippets/ICustomClasses.java"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(
        "package com.strategyquant.lib.snippets;\n"
        "public interface ICustomClasses {}\n"
    )
    command = [
        "docker", "run", "--rm", "--network", "none",
        "--mount", f"type=bind,src={internal_root.resolve()},dst=/sq/internal,readonly",
        "--mount", f"type=bind,src={output_dir},dst=/out",
        builder_image, "bash", "-lc",
        "set -euo pipefail; mkdir -p /out/classes; "
        "javac --release 22 -cp '/sq/internal/libs/*' -d /out/classes "
        "/out/src/com/strategyquant/lib/snippets/ICustomClasses.java "
        "/out/src/SQ/Internal/RulesImpl/Signal.java",
    ]
    completed = runner(command, capture_output=True, text=True, timeout=300, check=False)
    if completed.returncode != 0:
        raise RuntimeError("signal probe compilation failed: " + completed.stderr[-2000:])
    class_file = output_dir / "classes/SQ/Internal/RulesImpl/Signal.class"
    if not class_file.is_file():
        raise RuntimeError("signal probe outputs missing")
    class_header = class_file.read_bytes()[:8]
    if len(class_header) != 8 or class_header[:4] != b"\xca\xfe\xba\xbe" \
            or int.from_bytes(class_header[6:8], "big") != 66:
        raise RuntimeError("signal probe class is not Java 22")
    output_jar = output_dir / "Snippets.signal-probe.jar"
    _replace_class_deterministically(
        original_jar=original_jar, class_file=class_file, output_jar=output_jar)
    return {
        "schema_version": 1, "decision": "PASS_SIGNAL_PROBE_JAR",
        "production_sq_modified": False, "network_used_during_build": False,
        "builder_image": builder_image, "java_class_major_version": 66,
        "source_path": str(source.resolve()), "source_sha256": source_hash,
        "original_jar_path": str(original_jar.resolve()),
        "original_jar_sha256": _sha(original_jar),
        "patched_source_path": str(java), "patched_source_sha256": _sha(java),
        "output_jar_path": str(output_jar), "output_jar_sha256": _sha(output_jar),
        "log_environment_variable": "ALQUIMIA_SIGNAL_LOG_PATH",
        "log_schema": "sq_strategy_time_long;signal_variable_uuid;boolean_0_or_1",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--internal-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--builder-image", default="eclipse-temurin:22-jdk")
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = build(internal_root=args.internal_root, output_dir=args.output_dir,
                   builder_image=args.builder_image)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "output_jar_sha256": result["output_jar_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
