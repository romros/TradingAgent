import hashlib
from pathlib import Path
from lab.sq_bridge.xom_d1_price_action_pilot_v1 import compile_pilot

def test_build_is_reproducible(tmp_path:Path):
 a=compile_pilot(tmp_path/'a');b=compile_pilot(tmp_path/'b')
 assert a['project_sha256']==b['project_sha256']
 assert hashlib.sha256(Path(a['project']).read_bytes()).hexdigest()==a['project_sha256']
