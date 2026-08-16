#!/usr/bin/env python3
"""Materialize the preregistered NFLX 0.4681 one-axis SQX neighborhood."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_sqx(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, members[name])


def one(root: ET.Element, xpath: str) -> ET.Element:
    rows = root.findall(xpath)
    if len(rows) != 1:
        raise ValueError(f"expected one node for {xpath}, got {len(rows)}")
    return rows[0]


def materialize(source: Path, spec_path: Path, output_dir: Path) -> dict:
    spec = json.loads(spec_path.read_text())
    if sha(source) != spec["source_sqx_sha256"]:
        raise ValueError("source SQX hash mismatch")
    with zipfile.ZipFile(source) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    strategy_source = members["strategy_Portfolio.xml"]
    settings_source = members["settings.xml"]
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for patch in spec["neighbors"]:
        values = {**spec["central"], **{k: v for k, v in patch.items() if k != "id"}}
        strategy = ET.fromstring(strategy_source)
        settings = ET.fromstring(settings_source)
        action = one(strategy, ".//Rule[@name='Long entry']/Then/Item[@key='EnterAtStop']")
        price = one(action, "./Param[@key='#Price#']/Formula/Block/Item[@key='Plus']")
        highest = one(price, "./Block[@key='#Left#']/Item[@key='Highest']")
        entry_atr = one(price, "./Block[@key='#Right#']/Item[@key='Multiplication']/Block[@key='#Right#']/Item[@key='ATR']")
        buffer_number = one(price, "./Block[@key='#Right#']/Item[@key='Multiplication']/Block[@key='#Left#']/Item[@key='Number']/Param[@key='#Number#']")
        stop = one(action, "./Param[@key='#StopLoss.StopLoss#']/Formula[@key='SQ.Formulas.SLPT.ATRBasedValue']/Param[@key='#Value#']")
        target = one(action, "./Param[@key='#ProfitTarget.ProfitTarget#']/Formula[@key='SQ.Formulas.SLPT.ATRBasedValue']/Param[@key='#Value#']")
        one(highest, "./Param[@key='#Period#']").text = str(values["highest_period"])
        one(entry_atr, "./Param[@key='#Period#']").text = str(values["entry_atr_period"])
        buffer_number.text = f"{values['entry_atr_multiplier']:.2f}"
        stop.text = str(values["stop_atr_multiplier"])
        target.text = str(values["target_atr_multiplier"])
        candidate_id = f"NFLX04681_{patch['id']}"
        settings.set("ResultName", candidate_id)
        for node in settings.findall(".//StrategyName"):
            node.text = candidate_id
        for node in settings.findall(".//Fingerprint"):
            node.set("strategyName", candidate_id)
        target_path = output_dir / f"{candidate_id}.sqx"
        variant_members = dict(members)
        variant_members["strategy_Portfolio.xml"] = ET.tostring(
            strategy, encoding="utf-8", xml_declaration=True)
        variant_members["settings.xml"] = ET.tostring(
            settings, encoding="utf-8", xml_declaration=True)
        write_sqx(target_path, variant_members)
        rows.append({"id": patch["id"], "candidate_id": candidate_id,
                     "parameters": values, "sqx_path": str(target_path.resolve()),
                     "sqx_sha256": sha(target_path)})
    result = {"schema_version": 1, "decision": "PASS_NEIGHBORS_MATERIALIZED",
              "spec_path": str(spec_path.resolve()), "spec_sha256": sha(spec_path),
              "source_sqx_path": str(source.resolve()), "source_sqx_sha256": sha(source),
              "neighbors": rows, "performance_accessed": False,
              "holdout_2025_accessed": False, "paper_authorized": False,
              "live_authorized": False}
    manifest = output_dir / "materialization.manifest.json"
    manifest.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = materialize(args.source, args.spec, args.output_dir)
    print(json.dumps({"decision": result["decision"],
                      "neighbors": len(result["neighbors"])}, indent=2))


if __name__ == "__main__":
    main()
