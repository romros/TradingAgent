#!/usr/bin/env python3
"""Extreu evidència mínima d'un .sqx sense copiar l'estratègia ni stats binàries."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


def _params(item: ET.Element) -> dict:
    return {p.get("key", "").strip("#"): (p.text or "").strip() for p in item.findall("./Param")}


def extract(path: Path) -> dict:
    raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as archive:
        strategy = ET.fromstring(archive.read("strategy_Portfolio.xml"))
        results = ET.fromstring(archive.read("settings.xml"))
    blocks = []
    for item in strategy.findall(".//Item"):
        key = item.get("key")
        if key in {"EMA", "SMA", "ADX"}:
            entry = {"key": key, "params": _params(item)}
            if entry not in blocks:
                blocks.append(entry)
    formulas = []
    for formula in strategy.findall(".//Formula"):
        if "ATRBasedValue" in formula.get("key", ""):
            entry = {"type": "ATRBasedValue", "params": _params(formula)}
            if entry not in formulas:
                formulas.append(entry)
    # SQ serialitza un embolcall <Fingerprint type=...> i, dins seu, el valor
    # <Fingerprint trades=...>. No podem quedar-nos amb la primera coincidència.
    fingerprint = next(
        node for node in results.findall(".//Fingerprint") if node.get("trades") is not None
    )
    instrument = results.find(".//InstrumentInfo")
    settings = {node.tag: node.text for node in results.findall(".//Result/SettingsMap/*")}
    special = {node.tag: node.text for node in results.findall(".//SpecialValuesMap/SettingsMap/*")}
    def iso_millis(value: str | None) -> str | None:
        return datetime.fromtimestamp(int(value) / 1000, timezone.utc).date().isoformat() if value else None
    return {
        "candidate_id": results.find(".//StrategyName").text,
        "artifact_sha256": raw_hash,
        "sq_build": strategy.get("AppVersion"),
        "engine": strategy.find(".//Strategy").get("engine"),
        "logic": {"blocks": blocks, "atr_exits": formulas},
        "generation_result": {
            "history_from": iso_millis(special.get("HistoryFrom")),
            "history_to": iso_millis(special.get("HistoryTo")),
            "trades": int(fingerprint.get("trades")),
            "profit": float(fingerprint.get("profit")),
            "drawdown": float(fingerprint.get("drawdown")),
            "fitness": float(fingerprint.get("fitness")),
            "complexity": int(special["Complexity"]),
            "oos_present": bool(results.find(".//Fitnesses").get("OOS") != "0.0"),
        },
        "execution_assumptions": {
            "initial_capital": float(settings["MoneyManagement.InitialCapital"]),
            "result_slippage": float(settings["Slippage"]),
            "instrument": instrument.get("instrument"),
            "instrument_spread": float(instrument.get("defaultSpread")),
            "instrument_slippage": float(instrument.get("defaultSlippage")),
            "order_size_step": float(instrument.get("orderSizeStep")),
            "commission_xml": instrument.get("commissions"),
            "swap_xml": instrument.get("swap"),
        },
        "classification": "IS_CANDIDATE_NOT_FINALIST",
        "missing": ["validation", "oos", "sealed_holdout", "regime_breakdown", "current_ostium_repricing", "liquidation"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqx", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.sqx), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
