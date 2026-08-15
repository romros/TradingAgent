import datetime as dt
from lab.sq_bridge.aapl_intraday_confirmation_screen_v1 import metrics as intraday_metrics
from lab.sq_bridge.diversified_futures_tsmom_screen_v1 import capped_inverse_vol
from lab.sq_bridge.gold_tsmom_confirmation_screen_v1 import metrics as gold_metrics

def test_intraday_costs_can_reverse_small_gross_edge():
    prices={f'2025-01-{day:02d}':(100.0,100.05) for day in range(2,22)}
    result=intraday_metrics(prices,1000,.35,.0004)
    assert result['sessions']==20
    assert result['net_return']<0

def test_inverse_vol_weights_are_normalized_and_capped():
    points={'A':{'vol':.01},'B':{'vol':.10},'C':{'vol':.20},'D':{'vol':.30}}
    weights=capped_inverse_vol(points)
    assert abs(sum(weights.values())-1)<1e-12
    assert max(weights.values())<=.3+1e-12

def test_gold_metrics_compound_and_measure_drawdown():
    rows=[(dt.date(2025,1,2),.10,1,1),(dt.date(2025,2,3),-.20,1,0),(dt.date(2025,3,3),.10,1,0)]
    result=gold_metrics(rows)
    assert result['months']==3
    assert abs(result['total_return']-(1.1*.8*1.1-1))<1e-12
    assert abs(result['maximum_drawdown']-.2)<1e-12
