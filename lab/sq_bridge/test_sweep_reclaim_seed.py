from xml.etree import ElementTree as ET

from lab.sq_bridge.sweep_reclaim_seed import _clean_settings, _signal


def _scaffold():
    root = ET.Element("Root")
    for key in ("AND", "IsLower", "IsGreater"):
        ET.SubElement(root, "Item", {"key": key})
    for key in ("Low", "High", "Close"):
        item = ET.SubElement(root, "Item", {"key": key})
        ET.SubElement(item, "Param", {"key": "#Shift#"}).text = "2"
    for key in ("Lowest", "Highest"):
        item = ET.SubElement(root, "Item", {"key": key})
        for param, value in (("#ComputedFrom#", "0"), ("#Period#", "14"), ("#Shift#", "1")):
            ET.SubElement(item, "Param", {"key": param}).text = value
    return root


def test_fixed_signal_uses_closed_bar_and_excludes_it_from_range():
    signal = _signal(_scaffold(), "long", 20)
    conditions = signal.findall("Item")
    assert [node.get("key") for node in conditions] == ["IsLower", "IsGreater"]
    thresholds = []
    for condition in conditions:
        blocks = condition.findall("Block")
        assert [block.get("key") for block in blocks] == ["#Left#", "#Right#"]
        operands = [block.find("Item") for block in blocks]
        assert operands[0].find("./Param[@key='#Shift#']").text == "1"
        thresholds.append(operands[1])
    assert ET.tostring(thresholds[0]) == ET.tostring(thresholds[1])
    assert thresholds[0].find("./Param[@key='#ComputedFrom#']").text == "3"
    assert thresholds[0].find("./Param[@key='#Period#']").text == "20"
    assert thresholds[0].find("./Param[@key='#Shift#']").text == "2"


def test_settings_cleaner_removes_quantitative_scaffold_results():
    raw = b"""<ResultsGroup ResultName='old'><ResultsMap><Results><Result>
      <Fitnesses IS='1'/><ValuesMap><stats_x><SQStats/></stats_x><Symbol>XAU</Symbol></ValuesMap>
      <SettingsMap><StrategyName>old</StrategyName></SettingsMap></Result></Results></ResultsMap>
      <SpecialValuesMap><SettingsMap><Fingerprint/><MEC_IS_Main>old</MEC_IS_Main></SettingsMap></SpecialValuesMap>
    </ResultsGroup>"""
    cleaned = _clean_settings(raw, "new")
    root = ET.fromstring(cleaned)
    assert root.get("ResultName") == "new"
    assert root.find(".//StrategyName").text == "new"
    assert root.find(".//SQStats") is None
    assert root.find(".//Fingerprint") is None
    assert root.find(".//Fitnesses").get("IS") == "0.0"
