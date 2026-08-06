#!/usr/bin/env python3
from xml.etree import ElementTree as ET

from alquimia_retest import PERIOD_KEYS, _condition, _graft_resource_symbol, _require_resource_symbol, _select_all_input_strategies

assert set(PERIOD_KEYS) == {"train", "validation", "oos", "holdout"}
node = _condition("ProfitFactor", "Decimal2", ">=", 1.15)
assert node.find("./Left-Side/Column-Value").get("column") == "ProfitFactor"
assert node.find("Comparator").get("value") == ">="
assert node.find("./Right-Side/Numeric-Value").get("value") == "1.15"
dd_node = _condition("DrawdownPct", "Decimal2Pct", "<=", 20)
assert dd_node.find("./Left-Side/Column-Value").get("column") == "DrawdownPct"
assert dd_node.find("Comparator").get("value") == "<="
assert dd_node.find("./Right-Side/Numeric-Value").get("value") == "20"
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


def test_generator_source_forces_full_input_databank_not_stale_selection():
    source = ET.fromstring("""<Settings>
      <Databanks retestSelected='true'><Databank name='Input'/><Databank name='Output'/></Databanks>
      <SelectedStrategies><Strategy>STALE</Strategy></SelectedStrategies>
    </Settings>""")
    _select_all_input_strategies(source)
    databanks = source.find('./Databanks')
    assert databanks.get('retestSelected') == 'false'
    assert not source.findall('./SelectedStrategies/Strategy')
