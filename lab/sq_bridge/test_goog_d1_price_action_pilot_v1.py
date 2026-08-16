import json
from pathlib import Path
from lab.sq_bridge.goog_d1_price_action_pilot_v1 import compile_pilot

def test_compile_is_reproducible_and_blind(tmp_path):
 first=compile_pilot(tmp_path/'a');second=compile_pilot(tmp_path/'b')
 assert first['project_sha256']==second['project_sha256']
 manifest=json.loads(Path(first['manifest']).read_text())
 assert manifest['attempt_budget']==100000
 assert manifest['search_profile']=='equity_d1_trend_pullback_v1'
 assert manifest['sq_symbol']=='GOOG_IBKR_V1_D1'
 assert first['sqcli_started'] is False
