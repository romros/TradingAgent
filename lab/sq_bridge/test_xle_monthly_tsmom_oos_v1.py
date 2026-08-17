from pathlib import Path

from lab.sq_bridge.xle_monthly_tsmom_oos_v1 import evaluate


ROOT = Path(__file__).resolve().parents[2]


def test_frozen_xle_oos_decision_replays():
    result = evaluate(
        ROOT / "data/ibkr_sq_v2/etf_twelve_one_momentum_v1/adjusted/XLE_ADJUSTED_D1_2017_2024.csv",
        ROOT / "data/ibkr_sq_v2/xle_monthly_tsmom_v1/validation_screen.json",
    )
    assert result["decision"] == "REJECT_GROSS_OOS"
    assert result["results"]["M6"]["oos_2024"]["total_return"] < 0
    assert result["results"]["M12"]["oos_2024"]["total_return"] < 0
    assert result["holdout_2025_plus_accessed"] is False
    assert result["optimized"] is False
