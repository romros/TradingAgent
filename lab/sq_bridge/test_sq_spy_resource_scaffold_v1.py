import zipfile
import xml.etree.ElementTree as ET

from lab.sq_bridge.sq_spy_resource_scaffold_v1 import build


def test_builds_exact_quarantined_spy_resource(tmp_path):
    source = tmp_path / "source.cfx"
    task = b'''<Root><Resources><Symbols><Symbol name="OLD" uSymbol="OLD">
      <InstrumentInfo instrument="OLD" tickSize="1" pointValue="9" />
    </Symbol></Symbols></Resources></Root>'''
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("config.xml", b"<Project/>")
        archive.writestr("Retest-Task1.xml", task)
    output = tmp_path / "spy.cfx"
    receipt = build(source, output)
    with zipfile.ZipFile(output) as archive:
        root = ET.fromstring(archive.read("Retest-Task1.xml"))
    symbol = root.find("./Resources/Symbols/Symbol")
    assert symbol.get("name") == "SPY_benchmark.D"
    assert symbol.find("InstrumentInfo").get("pointValue") == "1.0"
    assert receipt["source_classification"] == "SQ_PROPRIETARY_QUARANTINE"
    assert receipt["ibkr_contract_verified"] is False
