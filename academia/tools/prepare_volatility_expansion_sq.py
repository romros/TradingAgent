#!/usr/bin/env python3
"""Prepare a cheap D1 volatility-expansion SQ campaign from risk-safe templates."""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


SIGNALS = {
    "ATRChangesDown",
    "ATRFalling",
    "BBBarClosesAboveUp",
    "BBBarClosesBelowDown",
}
OTHER_BLOCKS = {
    "Stop/Limit Price Ranges.ATR",
    "EnterAtMarket",
    "ExitAfterBars.ExitAfterBars",
    "StopLoss.StopLoss",
}
ALLOWED_BLOCKS = SIGNALS | OTHER_BLOCKS


def _text(root: ET.Element, path: str, value: str) -> None:
    node = root.find(path)
    if node is None:
        raise ValueError(f"missing SQ setting: {path}")
    node.text = value


def rewrite(files: dict[str, bytes], project_name: str) -> dict[str, bytes]:
    result = dict(files)
    config = ET.fromstring(result["config.xml"])
    config.set("name", project_name)
    result["config.xml"] = ET.tostring(config, encoding="utf-8", xml_declaration=True)

    root = ET.fromstring(result["Build-Task1.xml"])
    setups = root.findall(".//Setup")
    if len(setups) < 2:
        raise ValueError("expected main and dormant SQ setups")
    for setup in setups:
        setup.set("dateFrom", "2017.01.01")
        setup.set("dateTo", "2021.12.31")
        setup.set("testPrecision", "2")
        for chart in setup.findall("Chart"):
            chart.set("timeframe", "D1")

    crosschecks = root.find(".//CrossChecks")
    if crosschecks is None or crosschecks.get("use") != "false":
        raise ValueError("cheap generation requires disabled crosschecks")
    stop = root.find(".//Rankings/StopCondition")
    if stop is None:
        raise ValueError("missing stop condition")
    stop.attrib.update({
        "type": "databank-full", "passedStrategies": "20",
        "restartCount": "0", "days": "0", "hours": "0", "minutes": "10",
    })

    rules = root.find(".//RulesComplexity/Chart")
    if rules is None:
        raise ValueError("missing rules complexity")
    rules.attrib.update({"minConditions": "2", "maxConditions": "2",
                         "minExitConditions": "0", "maxExitConditions": "0",
                         "minExitTypes": "1", "maxExitTypes": "2"})
    sides = root.find(".//MarketSides")
    if sides is None:
        raise ValueError("missing market sides")
    sides.set("type", "both")
    _text(sides, "EntrySymmetry", "true")
    _text(sides, "ExitSymmetry", "true")

    _text(root, ".//SLPTOptions/SLRequired", "true")
    _text(root, ".//SLPTOptions/SLFixedPips", "false")
    _text(root, ".//SLPTOptions/SLATR", "true")
    _text(root, ".//SLPTOptions/MinSLATRMultiple", "1.5")
    _text(root, ".//SLPTOptions/MaxSLATRMultiple", "4")
    _text(root, ".//SLPTOptions/MinSLATRPeriod", "10")
    _text(root, ".//SLPTOptions/MaxSLATRPeriod", "50")
    _text(root, ".//SLPTOptions/PTRequired", "false")

    blocks = root.findall(".//Block")
    keys = {block.get("key") for block in blocks}
    missing = ALLOWED_BLOCKS - keys
    if missing:
        raise ValueError(f"template lacks required blocks: {sorted(missing)}")
    for block in blocks:
        block.set("use", str(block.get("key") in ALLOWED_BLOCKS).lower())

    methods = root.findall(".//RiskMoneyManagement/MoneyManagement/Method")
    active = [method for method in methods if method.get("use") == "true"]
    if len(active) != 1 or active[0].get("type") != "RiskFixedBalancePct":
        raise ValueError("template must already enforce RiskFixedBalancePct")
    risk = active[0].find(".//*[@key='Risk']")
    if risk is None or float(risk.text or "nan") != 1.0:
        raise ValueError("template must already enforce one-percent risk")
    risk_management = root.find(".//RiskMoneyManagement/RiskManagement")
    if risk_management is None or float(risk_management.get("maxDrawdown", "nan")) != 15.0:
        raise ValueError("template must already enforce 15-percent drawdown")

    result["Build-Task1.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return result


def prepare(template: Path, output: Path, project_name: str) -> Path:
    with ZipFile(template) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    target_dir = output / project_name
    if target_dir.exists():
        raise FileExistsError(f"refusing to overwrite prepared project: {target_dir}")
    rendered = rewrite(files, project_name)
    target_dir.mkdir(parents=True)
    target = target_dir / "project.cfx"
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for name, payload in rendered.items():
            archive.writestr(name, payload)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    args = parser.parse_args()
    print(prepare(args.template, args.output, args.project_name))


if __name__ == "__main__":
    main()
