#!/usr/bin/env python3
"""Create a venue-neutral SQX while preserving the exact strategy logic."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.sqx_extract import extract
from lab.sq_bridge.sqx_to_ir import canonical_ir, validate_executable_ir


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _unique(root: ET.Element, xpath: str, label: str) -> ET.Element:
    matches = root.findall(xpath)
    if len(matches) != 1:
        raise ValueError(f"{label} no es unic: {len(matches)}")
    return matches[0]


def _setting_node(settings: ET.Element, key: str) -> ET.Element:
    matches = settings.findall(f"./*[@key='{key}']")
    if not matches:
        matches = settings.findall(f"./{key}")
    if len(matches) != 1:
        raise ValueError(f"Setting {key} no es unic: {len(matches)}")
    return matches[0]


def _normalize_settings(raw: bytes, symbol: str) -> bytes:
    root = ET.fromstring(raw)
    settings = _unique(root, ".//Results/Result/SettingsMap", "SettingsMap principal")
    for key in ("ExitAtEndOfDay.ExitAtEndOfDay", "ExitOnFriday.ExitOnFriday"):
        node = _setting_node(settings, key)
        node.text = "false"
    slippage = _setting_node(settings, "Slippage")
    slippage.text = "0.0"
    swap = _unique(settings, "./Swap/Swap", "Swap")
    swap.attrib.update({"use": "false", "long": "0.0", "short": "0.0"})

    instrument = _unique(
        root, f".//SymbolsMap/SymbolInfo[@symbolName='{symbol}']/InstrumentInfo",
        "InstrumentInfo")
    instrument.set("defaultSpread", "0.0")
    instrument.set("defaultSlippage", "0.0")
    instrument.set(
        "commissions", '<Method type="None" use="true"><Params /></Method>')
    instrument.set(
        "swap", '<Swap use="false" type="money" long="0.0" short="0.0" '
                'tripleSwapOn="WEDNESDAY" rolloutHour="23:00" />')
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def normalize(*, source_path: Path, output_path: Path, receipt_path: Path,
              retest_receipt_path: Path | None = None) -> dict:
    source_contract = extract(source_path)
    if source_contract.get("translation_status") != "SUPPORTED_SUBSET":
        raise ValueError("SQX font fora del subset traduible")
    if output_path.stem != source_contract.get("strategy_name"):
        raise ValueError("El nom del fitxer SQX ha de coincidir amb StrategyName")
    retest_lineage = {}
    if retest_receipt_path is not None:
        retest = json.loads(retest_receipt_path.read_text())
        if (retest.get("decision") != "PASS_SUPERVISED_RETEST"
                or Path(retest.get("retest_output_sqx_path", "")).resolve()
                    != source_path.resolve()
                or retest.get("retest_output_sqx_sha256") != _sha(source_path)
                or retest.get("candidate_id") != source_contract.get("strategy_name")
                or retest.get("performance_filters_applied_in_sq") is not False
                or retest.get("total_tested") != 1):
            raise ValueError("Receipt del retest font no prova un resultat fresc")
        retest_lineage = {
            "source_retest_receipt_path": str(retest_receipt_path.resolve()),
            "source_retest_receipt_sha256": _sha(retest_receipt_path),
            "fresh_sq_retest_proven": True,
        }
    with zipfile.ZipFile(source_path) as source:
        names = source.namelist()
        if names.count("settings.xml") != 1 or names.count("strategy_Portfolio.xml") != 1:
            raise ValueError("SQX font no te membres unics")
        members = {info.filename: source.read(info.filename) for info in source.infolist()}
        infos = source.infolist()
    before_hashes = {name: _sha_bytes(payload) for name, payload in members.items()}
    members["settings.xml"] = _normalize_settings(
        members["settings.xml"], source_contract["market"]["symbol"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", allowZip64=True) as target:
        for info in infos:
            target.writestr(info, members[info.filename])
    temporary.replace(output_path)
    output_contract = extract(output_path)
    executable = validate_executable_ir(canonical_ir(output_contract))
    after_hashes = {name: _sha_bytes(payload) for name, payload in members.items()}
    changed = sorted(name for name in members if before_hashes[name] != after_hashes[name])
    if (changed != ["settings.xml"]
            or output_contract["strategy_xml_sha256"]
            != source_contract["strategy_xml_sha256"]
            or output_contract["strategy_name"] != source_contract["strategy_name"]
            or output_contract["market"] != source_contract["market"]):
        raise RuntimeError("La normalitzacio ha alterat quelcom fora de settings.xml")
    result = {
        "schema_version": 1,
        "decision": "PASS_VENUE_NEUTRAL_SQX",
        "normalization_role": ("configuration_metadata_after_fresh_sq_retest"
                               if retest_receipt_path is not None
                               else "configuration_only_before_fresh_sq_retest"),
        "performance_from_source_invalidated": True,
        "source_path": str(source_path.resolve()),
        "source_sha256": source_contract["source_sha256"],
        "output_path": str(output_path.resolve()),
        "output_sha256": _sha(output_path),
        "strategy_name": source_contract["strategy_name"],
        "strategy_xml_sha256": source_contract["strategy_xml_sha256"],
        "changed_members": changed,
        "source_member_sha256": before_hashes,
        "output_member_sha256": after_hashes,
        "normalized_execution": output_contract["execution"],
        "executable_contract": executable,
        **retest_lineage,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--retest-receipt", type=Path)
    args = parser.parse_args()
    result = normalize(source_path=args.source, output_path=args.output,
                       receipt_path=args.receipt,
                       retest_receipt_path=args.retest_receipt)
    print(json.dumps({key: result[key] for key in
                      ("decision", "strategy_name", "changed_members")}, indent=2))


if __name__ == "__main__":
    main()
