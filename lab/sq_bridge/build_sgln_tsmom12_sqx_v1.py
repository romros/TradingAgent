#!/usr/bin/env python3
"""Build exact calendar-month SGLN TSMOM12 SQX from a proven native template."""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NAME = "SGLN_TSMOM12_MONTHLY_NATIVE_V1"
LONG_ENTRY = "33333333-1111-1111-3333-333333333333"
LONG_EXIT = "33333333-1111-2222-3333-333333333333"

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def custom(key):
    node = ET.Element("Item", {"key": key, "returnType": "boolean"})
    ET.SubElement(node, "Param", {"key": "#Chart#"}).text = "0"
    ET.SubElement(node, "Param", {"key": "#Months#"}).text = "12"
    ET.SubElement(node, "Param", {"key": "#Shift#"}).text = "0"
    return node

def build(template: Path, output: Path) -> dict:
    with zipfile.ZipFile(template) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(members["strategy_Portfolio.xml"])
    root.find(".//Strategy").set("name", NAME)
    for variable, key in ((LONG_ENTRY, "AlquimiaMonthlyMomentumAbove"),
                          (LONG_EXIT, "AlquimiaMonthlyMomentumBelow")):
        signal = root.find(f".//Rule[@type='Signal']/signals/signal[@variable='{variable}']")
        if signal is None: raise ValueError(f"template lacks signal {variable}")
        signal.clear(); signal.set("variable", variable); signal.append(custom(key))
    action = root.find(".//Rule[@name='Long entry']/Then/Item")
    action.find("./Param[@key='#ExitAfterBars.ExitAfterBars#']").text = "0"
    for key in ("#StopLoss.StopLoss#", "#ProfitTarget.ProfitTarget#"):
        param = action.find(f"./Param[@key='{key}']")
        param.clear(); param.set("key", key); param.set("isFormula", "true")
        ET.SubElement(param, "Formula", {"key": "SQ.Formulas.SLPT.None"})
    members["strategy_Portfolio.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    settings = ET.fromstring(members["settings.xml"])
    strategy_name = settings.find(".//StrategyName")
    if strategy_name is not None: strategy_name.text = NAME
    settings.set("ResultName", NAME)
    members["settings.xml"] = ET.tostring(settings, encoding="utf-8", xml_declaration=True)
    retained = {name: data for name, data in members.items()
                if not name.startswith("Results/") and name not in {"orders.bin", "lastSettings.xml"}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in retained.items():
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    receipt = {"schema_version": 1, "classification": "NATIVE_SQX_PARITY_REQUIRED",
               "strategy": NAME,
               "rule": "on first trading bar of month: prior month-end close > exact month-end close 12 calendar months earlier => long; inverse => cash",
               "calendar_month_lookup": True, "fixed_trading_day_proxy": False,
               "template_sha256": sha(template), "output_sha256": sha(output),
               "performance_accessed": False, "paper_authorized": False, "live_authorized": False}
    output.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    print(json.dumps(build(args.template, args.output), indent=2))
if __name__ == "__main__": main()
