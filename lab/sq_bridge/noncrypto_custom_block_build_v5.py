#!/usr/bin/env python3
"""Generate and compile the six Alquimia v5 SQ entry families reproducibly."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "lab/sq_bridge/sq_custom_blocks_v5"
INTERNAL_ROOT = Path("/home/roman/dockers-SQ/6ACC10/internal")
OUTPUT_DIR = ROOT / "lab/sq_bridge/evidence/noncrypto_custom_blocks_v5"
RECEIPT = ROOT / "lab/sq_bridge/evidence/noncrypto_custom_blocks_v5.json"

FAMILIES = {
    "XauM15MacroCompressionBreakout": {
        "params": [("ChannelIndex", 0, 4), ("CompressionIndex", 0, 2)],
        "setup": "int[] channels={8,12,16,24,32}; double[] quantiles={.15,.25,.35};",
        "call": "AlquimiaV5Signals.xauCompressionBreakout(Chart, Shift, channels[ChannelIndex], quantiles[CompressionIndex])",
        "directions": ("Long", "Short")},
    "XauM15FailedShockReversion": {
        "params": [("ShockIndex", 0, 3), ("ReentryIndex", 0, 3)],
        "setup": "double[] shocks={1.5,2,2.5,3}; int[] windows={1,2,3,4};",
        "call": "AlquimiaV5Signals.xauFailedShock(Chart, Shift, shocks[ShockIndex], windows[ReentryIndex])",
        "directions": ("Long", "Short")},
    "UsdjpyM15SessionRangeBreakout": {
        "params": [("RangeIndex", 0, 3), ("TrendIndex", 0, 3)],
        "setup": "double[] ratios={.6,.8,1,1.2}; int[] trends={8,16,24,32};",
        "call": "AlquimiaV5Signals.usdjpySessionBreakout(Chart, Shift, ratios[RangeIndex], trends[TrendIndex])",
        "directions": ("Long", "Short")},
    "UsdjpyM15FailedSessionBreakReversion": {
        "params": [("WindowIndex", 0, 3), ("BufferIndex", 0, 3)],
        "setup": "int[] windows={1,2,3,4}; double[] buffers={0,.1,.2,.3};",
        "call": "AlquimiaV5Signals.usdjpyFailedBreak(Chart, Shift, windows[WindowIndex], buffers[BufferIndex])",
        "directions": ("Long", "Short")},
    "Us500D1VolatilityShockRebound": {
        "params": [("ShockIndex", 0, 3), ("ReclaimIndex", 0, 3)],
        "setup": "double[] shocks={1.5,2,2.5,3}; double[] reclaims={.25,.4,.55,.7};",
        "call": "AlquimiaV5Signals.us500ShockRebound(Chart, Shift, shocks[ShockIndex], reclaims[ReclaimIndex])",
        "directions": ("Long",)},
    "EurusdD1ShortHorizonTrend": {
        "params": [("ChannelIndex", 0, 4), ("TrendIndex", 0, 3)],
        "setup": "int[] channels={5,10,15,20,30}; int[] trends={5,10,20,40};",
        "call": "AlquimiaV5Signals.eurusdShortTrend(Chart, Shift, channels[ChannelIndex], trends[TrendIndex])",
        "directions": ("Long", "Short")},
}


def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def source(family: str, spec: dict, direction: str) -> str:
    name = f"AlquimiaV5{family}{direction}"
    opposite = f"AlquimiaV5{family}{'Short' if direction == 'Long' else 'Long'}"
    annotation = f'@OppositeBlock("{opposite}")\n' if len(spec["directions"]) == 2 else ""
    params = "\n".join(
        f'    @Parameter(defaultValue="0", minValue={low}, maxValue={high}, step=1) public int {param};'
        for param, low, high in spec["params"])
    wanted = "1" if direction == "Long" else "-1"
    return f'''package SQ.Blocks.Alquimia;
import SQ.Internal.ConditionBlock;
import SQ.Utils.AlquimiaV5Signals;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.*;
@BuildingBlock(name="(Alquimia v5) {family} {direction}", display="Alquimia v5 {family} {direction}", returnType=ReturnTypes.Boolean)
{annotation}@ForEngine("*,-SP,-SA")
public class {name} extends ConditionBlock {{
    @Parameter public ChartData Chart;
{params}
    @Parameter public int Shift;
    @Override public boolean OnBlockEvaluate() throws TradingException {{
        {spec['setup']}
        return {spec['call']} == {wanted};
    }}
}}
'''


def build(output_dir: Path = OUTPUT_DIR, receipt: Path = RECEIPT,
          runner=subprocess.run) -> dict:
    output_dir = output_dir.resolve(); generated = output_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    sources: list[Path] = []
    for family, spec in FAMILIES.items():
        for direction in spec["directions"]:
            path = generated / "SQ/Blocks/Alquimia" / f"AlquimiaV5{family}{direction}.java"
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source(family, spec, direction))
            sources.append(path)
    utility = SOURCE_ROOT / "SQ/Utils/AlquimiaV5Signals.java"
    if not utility.is_file() or not (INTERNAL_ROOT / "libs/Snippets.jar").is_file():
        raise ValueError("custom block source or SQ libraries missing")
    command = ["docker", "run", "--rm", "--network", "none",
        "--mount", f"type=bind,src={INTERNAL_ROOT.resolve()},dst=/sq/internal,readonly",
        "--mount", f"type=bind,src={SOURCE_ROOT.resolve()},dst=/src,readonly",
        "--mount", f"type=bind,src={generated},dst=/generated,readonly",
        "--mount", f"type=bind,src={output_dir},dst=/out", "eclipse-temurin:22-jdk",
        "bash", "-lc", "set -euo pipefail; rm -rf /out/classes; mkdir -p /out/classes; "
        "javac --release 22 -cp '/sq/internal/libs/*' -d /out/classes "
        "/src/SQ/Utils/AlquimiaV5Signals.java /generated/SQ/Blocks/Alquimia/*.java"]
    completed = runner(command, capture_output=True, text=True, timeout=300, check=False)
    if completed.returncode: raise RuntimeError(completed.stderr[-5000:])
    classes = sorted((output_dir / "classes/SQ").rglob("*.class"))
    if len(classes) != 12: raise RuntimeError(f"expected 12 classes, got {len(classes)}")
    bundle = output_dir / "AlquimiaNoncryptoCustomBlocks-v5.jar"
    with zipfile.ZipFile(bundle, "w") as archive:
        for path in classes:
            member = path.relative_to(output_dir / "classes").as_posix()
            info = zipfile.ZipInfo(member, (2026, 8, 11, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    original_snippets = INTERNAL_ROOT / "libs/Snippets.jar"
    merged = output_dir / "Snippets.alquimia-v5.jar"
    replacement = {path.relative_to(output_dir / "classes").as_posix(): path.read_bytes()
                   for path in classes}
    seen: set[str] = set()
    with zipfile.ZipFile(original_snippets) as source_archive, zipfile.ZipFile(merged, "w") as target:
        for info in source_archive.infolist():
            payload = replacement.get(info.filename, source_archive.read(info.filename))
            if info.filename in replacement: seen.add(info.filename)
            target.writestr(info, payload)
        for member in sorted(set(replacement) - seen):
            info = zipfile.ZipInfo(member, (2026, 8, 11, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, replacement[member])
    result = {"schema_version": 1, "decision": "PASS_CUSTOM_BLOCK_COMPILE",
        "families": 6, "condition_blocks": 11, "compiled_classes": len(classes),
        "bundle_path": str(bundle), "bundle_sha256": _sha(bundle),
        "original_snippets_sha256": _sha(original_snippets),
        "merged_snippets_path": str(merged), "merged_snippets_sha256": _sha(merged),
        "merged_snippets_is_ephemeral_override": True,
        "utility_sha256": _sha(utility),
        "generated_source_sha256": {path.name: _sha(path) for path in sources},
        "production_sq_modified": False, "network_used": False,
        "performance_accessed": False, "holdout_accessed": False,
        "installation_authorized": False, "next_gate": "COMPILE_AND_VERIFY_18_CFX"}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--receipt", type=Path, default=RECEIPT); args = parser.parse_args()
    print(json.dumps(build(args.output_dir, args.receipt), indent=2, sort_keys=True))
