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


def extract(path: Path, stage: str | None = None) -> dict:
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
    result_keys = [node.get("resultKey") for node in results.findall(".//Result")]
    is_portfolio = "Portfolio" in result_keys and len(result_keys) > 1
    symbol_infos = [
        {"symbol": node.get("symbolName"), "instrument": node.get("instrumentName")}
        for node in results.findall(".//SymbolInfo")
    ]
    settings = {node.tag: node.text for node in results.findall(".//Result/SettingsMap/*")}
    special = {node.tag: node.text for node in results.findall(".//SpecialValuesMap/SettingsMap/*")}
    def iso_millis(value: str | None) -> str | None:
        return datetime.fromtimestamp(int(value) / 1000, timezone.utc).date().isoformat() if value else None
    is_retester = settings.get("IsRetester") == "true"
    if is_portfolio:
        classification = "PORTFOLIO_ARTIFACT_NOT_LIVE_READY"
        missing = ["component_cost_audit", "correlation_stability", "sealed_holdout", "current_venue_repricing"]
    elif stage is None:
        classification = "RETESTED_WINDOW_UNLABELLED" if is_retester else "IS_CANDIDATE_NOT_FINALIST"
        missing = ["stage_label", "sealed_holdout", "regime_breakdown", "current_ostium_repricing", "liquidation"] if is_retester else ["validation", "oos", "sealed_holdout", "regime_breakdown", "current_ostium_repricing", "liquidation"]
    else:
        classification = f"{stage.upper()}_RESULT_NOT_LIVE_READY"
        remaining = {
            "discovery": ["validation", "oos", "sealed_holdout"],
            "validation": ["oos", "sealed_holdout"],
            "oos": ["sealed_holdout"],
            "holdout": [],
        }[stage]
        missing = remaining + ["regime_breakdown", "current_ostium_repricing", "liquidation"]
    return {
        "candidate_id": results.get("ResultName") if is_portfolio else results.find(".//StrategyName").text,
        "artifact_sha256": raw_hash,
        "sq_build": strategy.get("AppVersion"),
        "engine": strategy.find(".//Strategy").get("engine"),
        "logic": {"blocks": blocks, "atr_exits": formulas},
        "portfolio": {
            "is_portfolio": is_portfolio,
            "components": [key for key in result_keys if key != "Portfolio"],
            "symbols": symbol_infos,
        },
        "generation_result": {
            "history_from": iso_millis(special.get("HistoryFrom")),
            "history_to": iso_millis(special.get("HistoryTo")),
            "trades": int(fingerprint.get("trades")),
            "profit": float(fingerprint.get("profit")),
            "drawdown": float(fingerprint.get("drawdown")),
            "fitness": float(fingerprint.get("fitness")),
            "complexity": int(special["Complexity"]),
            "oos_present": bool(results.find(".//Fitnesses").get("OOS") != "0.0"),
            "is_retester": is_retester,
        },
        "execution_assumptions": {
            "initial_capital": float(settings["MoneyManagement.InitialCapital"]),
            "result_slippage": float(settings["Slippage"]),
            "instrument": None if is_portfolio else instrument.get("instrument"),
            "instrument_spread": None if is_portfolio else float(instrument.get("defaultSpread")),
            "instrument_slippage": None if is_portfolio else float(instrument.get("defaultSlippage")),
            "order_size_step": None if is_portfolio else float(instrument.get("orderSizeStep")),
            "commission_xml": None if is_portfolio else instrument.get("commissions"),
            "swap_xml": None if is_portfolio else instrument.get("swap"),
        },
        "classification": classification,
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqx", type=Path)
    parser.add_argument("--stage", choices=("discovery", "validation", "oos", "holdout"))
    args = parser.parse_args()
    print(json.dumps(extract(args.sqx, args.stage), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
