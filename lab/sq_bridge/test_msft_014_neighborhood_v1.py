import json
import zipfile
from xml.etree import ElementTree as ET

from lab.sq_bridge.msft_014_neighborhood_v1 import derive


def test_derives_exact_frozen_27_point_neighborhood(tmp_path):
    source = tmp_path / "source.sqx"
    strategy = b'''<Root><Strategy name="old"/><Item key="IsRising"><Param key="#Bars#">4</Param></Item><Param key="#StopLoss.StopLoss#"><Formula key="SQ.Formulas.SLPT.PctValue"><Param key="#Value#">1.4</Param></Formula></Param><Param key="#ProfitTarget.ProfitTarget#"><Formula key="SQ.Formulas.SLPT.ATRBasedValue"><Param key="#Value#">4.4</Param><Param key="#AtrPeriod#">20</Param></Formula></Param></Root>'''
    settings = b'<R ResultName="old"><StrategyName>old</StrategyName></R>'
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", strategy)
        archive.writestr("settings.xml", settings)
        archive.writestr("version.txt", "3")
        archive.writestr("orders.bin", b"stale")
    result = derive(source, tmp_path / "variants")
    assert result["variant_count"] == 27
    assert result["holdout_accessed"] is False
    center = tmp_path / "variants/MSFT014_B4_SL1.4_PT4.4.sqx"
    with zipfile.ZipFile(center) as archive:
        assert "orders.bin" not in archive.namelist()
        root = ET.fromstring(archive.read("strategy_Portfolio.xml"))
        assert root.find(".//Strategy").get("name") == center.stem
        assert root.find(".//Item[@key='IsRising']/Param[@key='#Bars#']").text == "4"
    lock = json.loads((tmp_path / "neighborhood_preregistration.lock.json").read_text())
    assert len(lock["sha256"]) == 64
