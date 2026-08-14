import json,subprocess,sys
from pathlib import Path
SCRIPT=Path(__file__).parents[1]/'lab/sq_bridge/sxr8_shadow_readiness.py'
def test_real_evidence_is_shadow_ready(tmp_path):
 root=Path(__file__).parents[1];out=tmp_path/'out.json';subprocess.run([sys.executable,str(SCRIPT),'--contract',str(root/'lab/sq_bridge/ibkr_sxr8_public_contract_v1.json'),'--research',str(root/'data/ibkr_sq_v2/turn_of_month/cspx_transfer_v1.json'),'--schedule',str(root/'data/ibkr_sq_v2/turn_of_month/sxr8_xetra_schedule_2026.json'),'--output',str(out)],check=True,capture_output=True);r=json.loads(out.read_text());assert r['decision']=='SHADOW_PAPER_READY' and r['orders_sent']==0 and not r['broker_account_required']
