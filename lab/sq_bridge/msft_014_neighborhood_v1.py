#!/usr/bin/env python3
"""Create the frozen local robustness neighborhood around MSFT Strategy 0.14."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from itertools import product
from pathlib import Path
from xml.etree import ElementTree as ET

BARS = (3, 4, 5)
STOPS = (1.2, 1.4, 1.6)
TARGETS = (4.0, 4.4, 4.8)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _one(root: ET.Element, path: str, label: str) -> ET.Element:
    rows = root.findall(path)
    if len(rows) != 1:
        raise ValueError(f"{label} must be unique")
    return rows[0]


def derive(source: Path, output_dir: Path) -> dict:
    raw = source.read_bytes()
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        base = {name: archive.read(name) for name in names}
    if names.count("strategy_Portfolio.xml") != 1 or names.count("settings.xml") != 1:
        raise ValueError("required SQX XML members must be unique")
    retained = [name for name in names if not name.startswith("Results/")
                and name not in {"orders.bin", "lastSettings.xml"}]
    output_dir.mkdir(parents=True, exist_ok=True)
    variants = []
    for bars, stop, target in product(BARS, STOPS, TARGETS):
        members = dict(base)
        strategy = ET.fromstring(members["strategy_Portfolio.xml"])
        rising = _one(strategy, ".//Item[@key='IsRising']", "IsRising")
        _one(rising, "./Param[@key='#Bars#']", "rising bars").text = str(bars)
        stop_formula = _one(
            strategy,
            ".//Param[@key='#StopLoss.StopLoss#']/Formula[@key='SQ.Formulas.SLPT.PctValue']",
            "percent stop")
        _one(stop_formula, "./Param[@key='#Value#']", "stop value").text = str(stop)
        target_formula = _one(
            strategy,
            ".//Param[@key='#ProfitTarget.ProfitTarget#']/Formula[@key='SQ.Formulas.SLPT.ATRBasedValue']",
            "ATR target")
        _one(target_formula, "./Param[@key='#Value#']", "target value").text = str(target)
        if _one(target_formula, "./Param[@key='#AtrPeriod#']", "ATR period").text != "20":
            raise ValueError("source ATR period must remain frozen at 20")
        variant_id = f"MSFT014_B{bars}_SL{stop:.1f}_PT{target:.1f}"
        _one(strategy, ".//Strategy", "Strategy").set("name", variant_id)
        settings = ET.fromstring(members["settings.xml"])
        _one(settings, ".//StrategyName", "StrategyName").text = variant_id
        settings.set("ResultName", variant_id)
        members["strategy_Portfolio.xml"] = ET.tostring(
            strategy, encoding="utf-8", xml_declaration=True)
        members["settings.xml"] = ET.tostring(
            settings, encoding="utf-8", xml_declaration=True)
        path = output_dir / f"{variant_id}.sqx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in retained:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100600 << 16
                archive.writestr(info, members[name])
        variants.append({"id": variant_id, "bars": bars, "stop_pct": stop,
                         "target_atr": target, "sqx_sha256": _sha(path.read_bytes())})
    result = {
        "schema_version": 1,
        "decision": "PREREGISTERED_LOCAL_NEIGHBORHOOD",
        "source_sqx_path": str(source.resolve()),
        "source_sqx_sha256": _sha(raw),
        "dimensions": {"rising_bars": list(BARS), "stop_pct": list(STOPS),
                       "target_atr20": list(TARGETS)},
        "variant_count": len(variants),
        "selection_rule": "No tuning: require broad positive validation and OOS region after IBKR costs; select a medoid, not the maximum.",
        "holdout_accessed": False,
        "variants": variants,
    }
    receipt = output_dir.parent / "neighborhood_preregistration.json"
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    (output_dir.parent / "neighborhood_preregistration.lock.json").write_text(
        json.dumps({"sha256": _sha(receipt.read_bytes())}, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive(args.source, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
