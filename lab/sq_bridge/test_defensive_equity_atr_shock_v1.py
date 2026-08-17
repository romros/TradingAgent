from lab.sq_bridge.defensive_equity_atr_shock_v1 import evaluate


def test_defensive_atr_shock_rejects_before_oos():
    result = evaluate()
    assert result["decision"] == "REJECT_DEVELOPMENT"
    assert result["pooled"]["train"]["profit_factor"] < 1
    assert result["pooled"]["validation"]["trades"] == 4
    assert result["oos_accessed"] is False
