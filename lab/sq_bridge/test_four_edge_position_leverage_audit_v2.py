from pathlib import Path

from four_edge_position_leverage_audit_v2 import audit


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/ibkr_sq_v2/four_edge_position_leverage_v1"


def test_frozen_position_only_leverage_replay():
    result = audit(
        DATA / "Portfolio-1786963273774.sqx",
        ROOT / "data/ibkr_sq_v2/four_edge_portfolio_composer_v1/ecb_gbpusd_2021_2024.csv",
        {key: DATA / f"orders-{key}-floor1000.csv" for key in ("cat", "msft", "jpm", "sgln")},
    )
    stress = result["scenarios"]["stress"]
    assert result["decision"] == "PASS_BEATS_SPY_POSITION_ONLY_LEVERAGE"
    assert result["positions"] == 93
    assert result["sgln_whole_shares_usd_corrected"] == 26
    assert stress["net_return_pct"] == 56.041808
    assert stress["daily_mtm_max_drawdown_pct"] == 15.915973
    assert stress["position_only_financing_usd"] == 21.667762
    assert stress["maximum_cash_borrow_usd"] == 1519.958396


def test_stress_is_worse_than_public_cost_scenarios():
    result = audit(
        DATA / "Portfolio-1786963273774.sqx",
        ROOT / "data/ibkr_sq_v2/four_edge_portfolio_composer_v1/ecb_gbpusd_2021_2024.csv",
        {key: DATA / f"orders-{key}-floor1000.csv" for key in ("cat", "msft", "jpm", "sgln")},
    )
    scenarios = result["scenarios"]
    assert scenarios["stress"]["net_return_pct"] < scenarios["fixed_indicative"]["net_return_pct"]
    assert scenarios["fixed_indicative"]["net_return_pct"] < scenarios["tiered_indicative"]["net_return_pct"]
    assert scenarios["stress"]["costs_usd"] > scenarios["fixed_indicative"]["costs_usd"]
