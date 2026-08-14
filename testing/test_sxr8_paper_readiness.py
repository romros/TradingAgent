import json,subprocess,sys
from pathlib import Path
SCRIPT=Path(__file__).parents[1]/'lab/sq_bridge/sxr8_paper_readiness.py'
def test_gate_blocks_without_account_evidence(tmp_path):
 values=[{'conid':75776072,'isin':'IE00B5BMR087','exchange':'IBIS2'},{'auth':{'authenticated':False},'candidates':[]},{'decision':{'by_listing':{'SXR8_DE':{'pass':True}}},'holdout_2025_accessed':False},{'actions':[{'idempotency_key':str(i)} for i in range(101)]}];paths=[]
 for i,v in enumerate(values):p=tmp_path/f'{i}.json';p.write_text(json.dumps(v));paths.append(p)
 out=tmp_path/'out.json';subprocess.run([sys.executable,str(SCRIPT),'--public-contract',str(paths[0]),'--account-probe',str(paths[1]),'--research',str(paths[2]),'--calendar',str(paths[3]),'--output',str(out)],check=True,capture_output=True);assert json.loads(out.read_text())['decision']=='PAPER_BLOCKED'
