from lab.sq_bridge.theoretical_strategy_library_v1 import build

def test_current_library_reflects_the_verified_four_edge_portfolio():
    result=build()
    assert result['evidence_verified'] is True
    assert result['portfolio_ready'] is True
    assert result['admitted_count']==3
    assert result['conditional_count']==2
    assert result['eligible_portfolio_count']==5
    assert 'aapl_momentum60_month_end_v1' in result['research_only_strategy_ids']
    assert 'aapl_h1_roc_4_1_174' in result['rejected_strategy_ids']
