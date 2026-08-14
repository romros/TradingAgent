import zipfile
from xml.etree import ElementTree as ET

from lab.sq_bridge.sqx_time_exit_variant_v2 import derive


def test_changes_only_logic_exit_and_sets_stable_variant_identity(tmp_path):
    source = tmp_path / "source.sqx"
    strategy = b"<S><Param key='#ExitAfterBars.ExitAfterBars#'>0</Param></S>"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", strategy)
        archive.writestr(
            "settings.xml",
            b"<Settings><StrategyName>parent</StrategyName></Settings>")
        archive.writestr("unchanged.bin", b"sentinel")
    output = tmp_path / "variant.sqx"
    result = derive(source, output, 24)
    with zipfile.ZipFile(output) as archive:
        root = ET.fromstring(archive.read("strategy_Portfolio.xml"))
        settings = ET.fromstring(archive.read("settings.xml"))
        assert archive.read("unchanged.bin") == b"sentinel"
    assert root.find(".//Param").text == "24"
    assert settings.findtext(".//StrategyName") == "variant"
    assert result["variant_id"] == "variant"
    assert result["source_strategy_xml_sha256"] != result["output_strategy_xml_sha256"]
