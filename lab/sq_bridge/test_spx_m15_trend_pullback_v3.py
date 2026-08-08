import pandas as pd

from spx_m15_trend_pullback_v3 import parameter_grid, rsi


def test_grid_matches_frozen_budget():
    config={"grid":{"side":["long","short"],"trend_ema_bars":[50,100],"rsi_bars":[2,3,5],
        "rsi_extreme":[5,10,20],"stop_atr":[1.5,2.0],"target_atr":[.5,1,1.5],
        "hold_bars":[8,16,24],"entry_window_ny":[[10,12],[10,14],[12,14]]}}
    assert len(list(parameter_grid(config))) == 1944


def test_rsi_reacts_to_direction():
    result=rsi(pd.Series([1,2,3,4,3,2,1,2,3],dtype=float),2)
    assert result.iloc[3] > result.iloc[6]
