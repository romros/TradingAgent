import json
from pathlib import Path
from lab.sq_bridge.alquimia_project import SEARCH_PROFILES

def test_nflx_breakout_contract_is_bounded_and_non_operational():
 spec=json.loads(Path('lab/sq_bridge/nflx_d1_volatility_breakout_v1.json').read_text())
 assert spec['discovery']['search_profile'] in SEARCH_PROFILES
 assert spec['discovery']['maximum_entry_rules'] <= 2
 assert spec['portfolio_gate']['maximum_total_strategies'] == 8
 assert spec['performance_accessed_for_this_family'] is False
 assert spec['paper_authorized'] is False and spec['live_authorized'] is False
