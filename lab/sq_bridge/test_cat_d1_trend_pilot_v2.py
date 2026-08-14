import json
import xml.etree.ElementTree as ET
import zipfile

from lab.sq_bridge.cat_d1_trend_pilot_v2 import compile_pilot


def test_cat_compiler_uses_frozen_d1_trade_gate(tmp_path):
    result = compile_pilot(tmp_path)
    assert result["decision"] == "PASS_THEORETICAL_DENSITY_PILOT_READY"
    with zipfile.ZipFile(tmp_path / "project.cfx") as archive:
        root = ET.fromstring(archive.read("Build-Task1.xml"))
    conditions = root.findall("./Tasks/Task/Config/Rankings/Conditions/Condition")
    # Support the CFX wrapper layout by falling back to any Rankings node.
    if not conditions:
        conditions = root.findall(".//Rankings/Conditions/Condition")
    observed = {row.find(".//Column-Value").get("column"):
                row.find(".//Numeric-Value").get("value") for row in conditions}
    assert observed["NumberOfTrades"] == "25"
    methodology = json.loads((tmp_path / "frozen_methodology.json").read_text())
    gate = methodology.get("hypothesis_screen", methodology["discovery"])
    assert gate["minimum_trades_train"] == 25
    assert gate["minimum_profit_factor_train"] == 1.05
