from pathlib import Path

from lab.sq_bridge.five_edge_residual_cash_v1 import evaluate


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/ibkr_sq_v2/four_edge_position_leverage_v1"


def test_frozen_cash_only_fifth_edge_replays():
    result = evaluate(
        DATA / "Portfolio-1786963273774.sqx",
        ROOT / "data/ibkr_sq_v2/four_edge_portfolio_composer_v1/ecb_gbpusd_2021_2024.csv",
        {key: DATA / f"orders-{key}-floor1000.csv" for key in ("cat", "msft", "jpm", "sgln")},
        ROOT / "lab/sq_bridge/multi_asset_known_edge_funnel_v1.json",
    )
    assert result["decision"] == "FAIL_FIFTH_EDGE_RESIDUAL_CASH"
    assert result["cagr_pct"] < result["base"]["cagr_pct"]
    assert result["daily_mtm_max_drawdown_pct"] > result["base"]["drawdown_pct"]
    assert result["policy"]["borrow_limit_usd"] == 0
    assert result["candidate"]["extra_financing_usd"] == 0
    assert result["paper_authorized"] is False
