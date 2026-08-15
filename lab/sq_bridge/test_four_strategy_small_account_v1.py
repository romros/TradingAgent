import json
from pathlib import Path

from four_strategy_small_account_v1 import audit, gold_whole_units


ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "data/ibkr_sq_v2/preflight/CATUSUSD_CANONICAL_D1_2017_2025.csv"
MSFT = ROOT / "data/ibkr_sq_v2/preflight/MSFT_ADJUSTED_D1_through_2024.csv"
JPM = ROOT / "data/ibkr_sq_v2/jpm_momentum60_v1/JPMUSUSD_CANONICAL_D1_through_2026.csv"
GOLD = ROOT / "data/ibkr_sq_v2/preflight/SGLN_L_ADJUSTED_D1_through_2024.csv"


def test_small_capital_cannot_reproduce_all_four_strategies():
    result = audit(CAT, MSFT, JPM, GOLD, 1000)
    assert not result["operationally_viable"]
    assert "CAT_0168" in result["strategies_with_zero_executions"]


def test_two_thousand_is_first_tested_viable_grid_point():
    lower = audit(CAT, MSFT, JPM, GOLD, 1500)
    viable = audit(CAT, MSFT, JPM, GOLD, 2000)
    assert not lower["operationally_viable"]
    assert viable["operationally_viable"]
    assert viable["events"] == 128
    assert viable["return_pct"] > 20
    assert viable["max_drawdown_pct_closed_equity"] < 10


def test_gold_uses_whole_units_and_has_no_hidden_fractional_notional():
    rows = gold_whole_units(GOLD, 125, "2022-01-01", "2024-12-31")
    assert len(rows) == 36
    assert rows[-1]["equity"] > 125


def test_durable_report_keeps_live_disabled():
    report = json.loads((ROOT / "data/ibkr_sq_v2/gold_tsmom_confirmation_v1/four_strategy_small_account_v1.json").read_text())
    assert report["paper_authorized"] is False
    assert report["live_authorized"] is False
    assert report["optimized"] is False
