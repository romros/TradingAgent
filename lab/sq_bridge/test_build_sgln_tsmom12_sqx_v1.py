import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_sgln_tsmom12_sqx_v1 import build, NAME, LONG_ENTRY, LONG_EXIT

ROOT = Path(__file__).resolve().parents[2]

def test_build_exact_monthly_native_shell(tmp_path):
    source = ROOT / "data/ibkr_sq_v2/jpm_momentum60_v1/JPM_MOMENTUM60_MONTH_END_V1.sqx"
    output = tmp_path / "sgln.sqx"
    receipt = build(source, output)
    with zipfile.ZipFile(output) as archive:
        root = ET.fromstring(archive.read("strategy_Portfolio.xml"))
        names = set(archive.namelist())
    assert root.find(".//Strategy").get("name") == NAME
    assert root.find(f".//signal[@variable='{LONG_ENTRY}']/Item").get("key") == "AlquimiaMonthlyMomentumAbove"
    assert root.find(f".//signal[@variable='{LONG_EXIT}']/Item").get("key") == "AlquimiaMonthlyMomentumBelow"
    assert "orders.bin" not in names and not any(name.startswith("Results/") for name in names)
    assert receipt["fixed_trading_day_proxy"] is False

def test_extension_uses_calendar_month_not_252_bar_proxy():
    source = (ROOT / "lab/sq_bridge/sq_extensions/SQ/Utils/AlquimiaMonthlyMomentum.java").read_text()
    assert "minusMonths(months)" in source
    assert "252" not in source and "253" not in source
