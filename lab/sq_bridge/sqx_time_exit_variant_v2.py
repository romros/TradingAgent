#!/usr/bin/env python3
"""Derive an auditable SQX variant changing only ExitAfterBars."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def derive(source: Path, output: Path, bars: int) -> dict:
    if not isinstance(bars, int) or isinstance(bars, bool) or not 1 <= bars <= 240:
        raise ValueError("time exit bars must be 1..240")
    source_raw = source.read_bytes()
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        members = {name: archive.read(name) for name in names}
    strategy_member = "strategy_Portfolio.xml"
    settings_member = "settings.xml"
    if names.count(strategy_member) != 1:
        raise ValueError("strategy_Portfolio.xml must be unique")
    if names.count(settings_member) != 1:
        raise ValueError("settings.xml must be unique")
    strategy = ET.fromstring(members[strategy_member])
    params = strategy.findall(".//Param[@key='#ExitAfterBars.ExitAfterBars#']")
    if len(params) != 1 or (params[0].text or "").strip() != "0":
        raise ValueError("source must have exactly one disabled ExitAfterBars")
    before_strategy = members[strategy_member]
    params[0].text = str(bars)
    # SQ writes the XML declaration back during Retest.  Include it now so the
    # strategy payload remains byte-identical after the round trip.
    members[strategy_member] = ET.tostring(
        strategy, encoding="utf-8", xml_declaration=True)

    # SQ uses the SQX filename as the databank identity on import/export.  Give
    # every derived variant that same explicit identity instead of retaining
    # the parent name and later weakening the supervisor's identity checks.
    variant_id = output.stem
    settings = ET.fromstring(members[settings_member])
    strategy_names = settings.findall(".//StrategyName")
    if len(strategy_names) != 1:
        raise ValueError("settings.xml must contain one StrategyName")
    strategy_names[0].text = variant_id
    members[settings_member] = ET.tostring(
        settings, encoding="utf-8", xml_declaration=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, members[name])
    result = {
        "schema_version": 1,
        "transformation": "EXIT_AFTER_BARS_ONLY",
        "source_sqx_path": str(source.resolve()),
        "source_sqx_sha256": _sha(source_raw),
        "source_strategy_xml_sha256": _sha(before_strategy),
        "output_sqx_path": str(output.resolve()),
        "output_sqx_sha256": _sha(output.read_bytes()),
        "output_strategy_xml_sha256": _sha(members[strategy_member]),
        "variant_id": variant_id,
        "exit_after_bars": bars,
        "oos_2024_accessed": False,
        "holdout_2025_accessed": False,
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--bars", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive(args.source, args.output, args.bars), indent=2))


if __name__ == "__main__":
    main()
