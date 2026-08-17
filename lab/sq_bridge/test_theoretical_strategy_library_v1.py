from lab.sq_bridge.theoretical_strategy_library_v1 import build

def test_current_library_reflects_the_verified_five_edge_portfolio():
    result=build()
    assert result['evidence_verified'] is True
    assert result['portfolio_ready'] is True
    assert result['admitted_count']==5
    assert result['conditional_count']==1
    assert result['eligible_portfolio_count']==6
    assert result['capped_portfolio_component_ids']==[
        'sgln_tsmom12_capped_v1',
        'nflx_d1_volatility_breakout_04681_capped_v1',
    ]
    assert 'aapl_momentum60_month_end_v1' in result['research_only_strategy_ids']
    assert 'aapl_h1_roc_4_1_174' in result['rejected_strategy_ids']
