from lab.sq_bridge.theoretical_strategy_library_v1 import build

def test_current_library_is_honestly_not_ready():
    result=build()
    assert result['evidence_verified'] is True
    assert result['portfolio_ready'] is False
    assert result['admitted_count']==2
    assert result['conditional_count']==1
    assert 'aapl_h1_roc_4_1_174' in result['rejected_strategy_ids']
