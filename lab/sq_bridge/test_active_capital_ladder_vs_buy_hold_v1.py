from pathlib import Path
from lab.sq_bridge.active_capital_ladder_vs_buy_hold_v1 import evaluate

def test_capital_ladder_keeps_objectives_separate():
 result=evaluate(Path('lab/sq_bridge/active_capital_ladder_vs_buy_hold_v1.json'))
 assert set(result['levels']) == {'1000','2000','3000'}
 assert result['recommended_capital_for_raw_outperformance_usd'] is None
 assert result['interpretation'].startswith('Defensive utility is not')
 assert result['paper_authorized'] is False
