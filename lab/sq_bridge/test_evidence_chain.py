import json
from pathlib import Path
import tempfile
import subprocess
import pytest
from lab.sq_bridge.evidence_chain import append_receipt,new_chain,verify

M=Path(__file__).with_name('methodology_v3.json')

def artifact(tmp,name):
 p=tmp/name; p.write_text(json.dumps({'name':name})); return p

def test_full_native_chain_requires_exact_translation_and_parity(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'c1','h1','XAUUSD')
 ids=['a','b']
 for stage in m['stages']:
  if stage=='temporal_validation': ids=['a']
  c=append_receipt(c,m,stage,artifact(tmp_path,stage+'.json'),'PASS',ids,
   holdout_accessed=stage in {'python_translation','parity','paper'},
   translation_exact=True if stage=='python_translation' else None,
   parity_pass=True if stage=='parity' else None)
 result=verify(c,M); assert result['valid']; assert result['paper_ready']; assert not result['live_authorized']

def test_rejection_is_terminal_and_skips_downstream_work(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'c2','h2','XAUUSD')
 c=append_receipt(c,m,'market_preflight',artifact(tmp_path,'market.json'),'PASS',[])
 c=append_receipt(c,m,'discovery',artifact(tmp_path,'discovery.json'),'REJECT',[])
 result=verify(c,M); assert result['valid']; assert result['terminal']; assert result['next_stage'] is None
 with pytest.raises(ValueError,match='TERMINAL_CHAIN'): append_receipt(c,m,'temporal_validation',artifact(tmp_path,'later.json'),'PASS',[])

def test_hash_tampering_and_candidate_swap_are_rejected(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'c3','h3','EURUSD')
 first=artifact(tmp_path,'market.json'); c=append_receipt(c,m,'market_preflight',first,'PASS',[])
 c=append_receipt(c,m,'discovery',artifact(tmp_path,'d.json'),'PASS',['sq-1'])
 with pytest.raises(ValueError,match='CANDIDATE_LINEAGE'): append_receipt(c,m,'temporal_validation',artifact(tmp_path,'v.json'),'PASS',['sq-2'])
 first.write_text('tampered'); assert 'ARTIFACT_HASH:0' in verify(c,M)['errors']

def test_legacy_quantitative_evidence_cannot_promote(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'c4','h4','XAUUSD','legacy_example')
 c=append_receipt(c,m,'market_preflight',artifact(tmp_path,'legacy.json'),'PASS',[])
 assert 'LEGACY_EXAMPLE_CANNOT_PROMOTE' in verify(c,M)['errors']

def test_cli_builds_reproducible_chain_without_overwriting_input(tmp_path):
 initial=tmp_path/'00.json'; first=tmp_path/'01.json'; evidence=artifact(tmp_path,'market.json')
 subprocess.run(['python3','-m','lab.sq_bridge.evidence_chain','new','--methodology',str(M),'--campaign','cli','--hypothesis','h','--market','XAUUSD','--output',str(initial)],check=True,capture_output=True,text=True)
 subprocess.run(['python3','-m','lab.sq_bridge.evidence_chain','append',str(initial),'--methodology',str(M),'--stage','market_preflight','--artifact',str(evidence),'--decision','PASS','--output',str(first)],check=True,capture_output=True,text=True)
 assert json.loads(initial.read_text())['receipts']==[]
 result=verify(json.loads(first.read_text()),M)
 assert result['valid'] and result['next_stage']=='discovery'
 failed=subprocess.run(['python3','-m','lab.sq_bridge.evidence_chain','append',str(first),'--methodology',str(M),'--stage','discovery','--artifact',str(evidence),'--decision','PASS','--output',str(first)],capture_output=True,text=True)
 assert failed.returncode!=0 and 'CHAIN_INPUT_OUTPUT_MUST_DIFFER' in failed.stderr
