#!/usr/bin/env python3
from xml.etree import ElementTree as ET

from alquimia_retest import PERIOD_KEYS, _condition, _graft_resource_symbol, _require_resource_symbol

assert set(PERIOD_KEYS) == {"validation", "oos", "holdout"}
node = _condition("ProfitFactor", "Decimal2", ">=", 1.15)
assert node.find("./Left-Side/Column-Value").get("column") == "ProfitFactor"
assert node.find("Comparator").get("value") == ">="
assert node.find("./Right-Side/Numeric-Value").get("value") == "1.15"
resources = ET.fromstring("<Settings><Resources><Symbols><Symbol/></Symbols></Resources></Settings>")
resources.find("./Resources/Symbols/Symbol").set("name", "XAU")
_require_resource_symbol(resources, "XAU")
try:
    _require_resource_symbol(resources, "TSLA")
except ValueError as exc:
    assert "RESOURCE_SYMBOL_MISMATCH" in str(exc)
else:
    raise AssertionError("cal rebutjar un chart sense recurs exacte")
target = ET.fromstring("<Settings><Resources><Symbols><Symbol name='EUR'/></Symbols></Resources></Settings>")
source = ET.fromstring("<Settings><Resources><Symbols><Symbol name='XAU'><InstrumentInfo instrument='XAUUSD'/></Symbol></Symbols></Resources></Settings>")
_graft_resource_symbol(target, source, "XAU")
assert [node.get("name") for node in target.findall("./Resources/Symbols/Symbol")] == ["XAU"]
assert target.find("./Resources/Symbols/Symbol/InstrumentInfo").get("instrument") == "XAUUSD"
print("PASS: temporal retest gates")
