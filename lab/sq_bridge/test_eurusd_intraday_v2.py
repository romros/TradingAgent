import pandas as pd

from lab.sq_bridge.eurusd_intraday_v2 import candidates, metrics


def test_pilot_has_ten_frozen_variants():
    rows=candidates()
    assert len(rows)==10
    assert {x[0] for x in rows}=={'asian_range_breakout','vol_expansion_continuation','vol_expansion_reversal'}


def test_metrics_charges_cost_against_risk_sized_notional():
    t=pd.DataFrame({'date':pd.to_datetime(['2020-01-01','2020-01-02'],utc=True),
                    'gross':[.01,-.005],'stop':[.01,.01]})
    m=metrics(t,0)
    assert m['n']==2
    assert m['ev_usdc']==.5
    assert m['pf']==2.0
