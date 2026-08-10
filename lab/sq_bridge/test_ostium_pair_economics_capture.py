from pathlib import Path

from lab.sq_bridge.ostium_small_account_cost_gate_v4 import REQUIRED_NOTIONALS_USDC


def test_default_capture_covers_full_200_usdc_margin_ceiling():
    script = (Path(__file__).parents[2] / "scripts" /
              "capture_ostium_pair_economics.sh").read_text()
    expected = ",".join(str(value) for value in REQUIRED_NOTIONALS_USDC)
    assert f"OSTIUM_NOTIONALS:-{expected}" in script
