import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_frozen_goog_marginal_decision_receipt():
    result = json.loads(
        (ROOT / "data/ibkr_sq_v2/goog_momentum60_residual_margin_v1/result.json").read_text()
    )
    assert result["decision"] == "FAIL_GOOG_MOMENTUM60_MARGINAL"
    assert result["cagr_pct"] > result["base"]["cagr_pct"]
    assert result["daily_mtm_max_drawdown_pct"] > 20
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
