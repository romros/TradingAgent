import json
from lab.sq_bridge.five_edge_portfolio_v1 import evaluate

def test_canonical_five_edge_aggregation_passes():
    result=evaluate(__import__('pathlib').Path('lab/sq_bridge/five_edge_portfolio_v1.json'))
    assert result['decision']=='PASS_FIVE_EDGE_THEORETICAL_PORTFOLIO'
    assert round(result['combined_net_return_pct'],4)==19.3155
    assert result['drawdown_budget_is_not_observed_portfolio_drawdown'] is True
