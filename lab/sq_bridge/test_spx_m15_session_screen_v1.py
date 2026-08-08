import pandas as pd

from spx_m15_session_screen_v1 import metrics, profit_factor


def test_profit_factor_and_costs():
    values = pd.Series([0.02, -0.01, 0.01])
    assert profit_factor(values) == 3
    frame = pd.DataFrame({"year": [2020, 2020, 2021], "r": values})
    result = metrics(frame, "r", 10)
    assert result["trades"] == 3
    assert result["positive_years"] == 2
    assert result["mean_net_bps"] == 56.666667
