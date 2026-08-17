from pathlib import Path

from lab.sq_bridge.ibtm_tsmom12_screen_v1 import run


ROOT = Path(__file__).resolve().parents[2]


def test_ibtm_exact_tsmom12_transfer_is_rejected():
    result = run(ROOT / "data/ibkr_sq_v2/preflight/IBTM_L_ADJUSTED_D1_through_2024.csv")
    assert result["decision"] == "REJECT_IBTM_TSMOM12"
    assert result["rule_transfer_changed"] is False
    assert result["periods"]["validation"]["total_return"] < 0
    assert result["periods"]["oos"]["total_return"] > 0
    assert result["periods"]["combined"]["annualized_sharpe"] < 0.4
