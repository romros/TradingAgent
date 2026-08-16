from pathlib import Path
from lab.sq_bridge.five_edge_vs_buy_hold_v1 import evaluate

def test_frozen_benchmark_is_deterministic_and_non_operational():
 result=evaluate(Path('lab/sq_bridge/five_edge_vs_buy_hold_v1.json'))
 assert result['spy_buy_hold_total_return']['shares'] > 0
 assert result['comparison']['drawdown_ratio_active_to_benchmark'] > 0
 assert result['benchmark_role'] == 'comparison_only_not_strategy_candidate'
 assert result['paper_authorized'] is False
 assert result['live_authorized'] is False
