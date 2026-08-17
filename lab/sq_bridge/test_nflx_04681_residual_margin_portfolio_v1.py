import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_nflx_marginal_receipt_is_safe_and_consistent():
    result = json.loads((ROOT / "data/ibkr_sq_v2/nflx_04681_residual_margin_portfolio_v1/result.json").read_text())
    assert result["decision"] == "PASS_NFLX_04681_MARGINAL_GATE"
    assert result["candidate"]["signals"] == (
        result["candidate"]["executed_trades"]
        + result["candidate"]["skipped_notional_cap"]
        + result["candidate"]["skipped_account_margin"]
    )
    assert result["minimum_equity_usd"] > 0
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
