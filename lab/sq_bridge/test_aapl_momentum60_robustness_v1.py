import json
from lab.sq_bridge.aapl_momentum60_robustness_v1 import run
def test_bootstrap_is_deterministic(tmp_path):
 p=tmp_path/'x.json';p.write_text(json.dumps({'trades':[{'net_return':v} for v in [.1]*8+[-.05]*2]}))
 assert run(p,runs=100,seed=7)==run(p,runs=100,seed=7)
 assert run(p,runs=100,seed=7)['trades']==10
