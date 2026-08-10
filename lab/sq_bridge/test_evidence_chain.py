import json
from pathlib import Path
import tempfile
import subprocess
import pytest
from lab.sq_bridge.evidence_chain import append_receipt,new_chain,verify

M=Path(__file__).with_name('methodology_v3.json')

def artifact(tmp,name,payload=None):
 p=tmp/name; p.write_text(json.dumps(payload or {'name':name})); return p

def pass_payload(stage,campaign,ids,holdout=False,evidence_class='observed'):
 common={"schema_version":1,"stage":stage,"campaign_id":campaign,"decision":"PASS",
  "candidate_ids":ids,"holdout_accessed":holdout,"evidence_class":evidence_class}
 if evidence_class=='synthetic_control': common['control_purpose']='pipeline_wiring_only'
 fields={
  "market_preflight":{"market_executable":True,"data_gate":"PASS","ostium_pair_id":"1"},
  "discovery":{"generator":"StrategyQuant","attempted":100,"selected_candidate_ids":ids},
  "temporal_validation":{"oos_trades":40,"positive_windows_ratio":.75,"oos_profit_factor":1.3,
   "oos_drawdown_pct":10,"train_oos_expectancy_decay_pct":20},
  "robustness":{"monte_carlo_runs":1000,"profitable_monte_carlo_ratio":.8,
   "parameter_perturbation_pct":10,"cost_stress_multiplier":2,"stress_profit_factor":1.1,
   "liquidation_probability":0},
  "small_account_economics":{"capital_usdc":200,"net_expectancy_usdc":.2,"net_profit_factor":1.2,
   "risk_per_trade_pct":1,"portfolio_margin_pct":20,"reserve_pct":60,"selected_leverage":5},
  "python_translation":{"translation_exact":True,"supported_subset":True,"sqx_sha256":"a"*64,
   "canonical_ir_sha256":"b"*64},
  "parity":{"parity_pass":True,"signal_match_rate":1.0,"trade_match_rate":1.0,
   "candle_coverage_pct":99,"pnl_correlation":.999},
  "paper":{"mode":"paper","paper_probe_configured":True,"live_authorized":False},
 }
 common.update(fields[stage]); return common

def test_full_native_chain_requires_exact_translation_and_parity(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'c1','h1','XAUUSD')
 ids=['a','b']
 for stage in m['stages']:
  if stage=='temporal_validation': ids=['a']
  holdout=stage in {'python_translation','parity','paper'}
  c=append_receipt(c,m,stage,artifact(tmp_path,stage+'.json',pass_payload(stage,'c1',ids,holdout)),'PASS',ids,
   holdout_accessed=holdout,
   translation_exact=True if stage=='python_translation' else None,
   parity_pass=True if stage=='parity' else None)
 result=verify(c,M); assert result['valid']; assert result['paper_ready']; assert not result['live_authorized']

def test_rejection_is_terminal_and_skips_downstream_work(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'c2','h2','XAUUSD')
 c=append_receipt(c,m,'market_preflight',artifact(tmp_path,'market.json',pass_payload('market_preflight','c2',[])),'PASS',[])
 rejected=pass_payload('discovery','c2',[]); rejected['decision']='REJECT'
 c=append_receipt(c,m,'discovery',artifact(tmp_path,'discovery.json',rejected),'REJECT',[])
 result=verify(c,M); assert result['valid']; assert result['terminal']; assert result['next_stage'] is None
 with pytest.raises(ValueError,match='TERMINAL_CHAIN'): append_receipt(c,m,'temporal_validation',artifact(tmp_path,'later.json'),'PASS',[])

def test_hash_tampering_and_candidate_swap_are_rejected(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'c3','h3','EURUSD')
 first=artifact(tmp_path,'market.json',pass_payload('market_preflight','c3',[])); c=append_receipt(c,m,'market_preflight',first,'PASS',[])
 c=append_receipt(c,m,'discovery',artifact(tmp_path,'d.json',pass_payload('discovery','c3',['sq-1'])),'PASS',['sq-1'])
 with pytest.raises(ValueError,match='CANDIDATE_LINEAGE'): append_receipt(c,m,'temporal_validation',artifact(tmp_path,'v.json'),'PASS',['sq-2'])
 first.write_text('tampered'); assert 'ARTIFACT_HASH:0' in verify(c,M)['errors']

def test_legacy_quantitative_evidence_cannot_promote(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'c4','h4','XAUUSD','legacy_example')
 c=append_receipt(c,m,'market_preflight',artifact(tmp_path,'legacy.json',pass_payload('market_preflight','c4',[])),'PASS',[])
 assert 'LEGACY_EXAMPLE_CANNOT_PROMOTE' in verify(c,M)['errors']

def test_cli_builds_reproducible_chain_without_overwriting_input(tmp_path):
 initial=tmp_path/'00.json'; first=tmp_path/'01.json'; evidence=artifact(tmp_path,'market.json',pass_payload('market_preflight','cli',[]))
 subprocess.run(['python3','-m','lab.sq_bridge.evidence_chain','new','--methodology',str(M),'--campaign','cli','--hypothesis','h','--market','XAUUSD','--output',str(initial)],check=True,capture_output=True,text=True)
 subprocess.run(['python3','-m','lab.sq_bridge.evidence_chain','append',str(initial),'--methodology',str(M),'--stage','market_preflight','--artifact',str(evidence),'--decision','PASS','--output',str(first)],check=True,capture_output=True,text=True)
 assert json.loads(initial.read_text())['receipts']==[]
 result=verify(json.loads(first.read_text()),M)
 assert result['valid'] and result['next_stage']=='discovery'
 failed=subprocess.run(['python3','-m','lab.sq_bridge.evidence_chain','append',str(first),'--methodology',str(M),'--stage','discovery','--artifact',str(evidence),'--decision','PASS','--output',str(first)],capture_output=True,text=True)
 assert failed.returncode!=0 and 'CHAIN_INPUT_OUTPUT_MUST_DIFFER' in failed.stderr

def test_strict_contract_rejects_insufficient_monte_carlo(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'strict','h','XAUUSD'); ids=['a']
 for stage in m['stages'][:3]:
  c=append_receipt(c,m,stage,artifact(tmp_path,stage+'.json',pass_payload(stage,'strict',ids if stage!='market_preflight' else [])),'PASS',ids if stage!='market_preflight' else [])
 bad=pass_payload('robustness','strict',ids); bad['monte_carlo_runs']=50
 c=append_receipt(c,m,'robustness',artifact(tmp_path,'robustness.json',bad),'PASS',ids)
 result=verify(c,M)
 assert not result['valid']
 assert 'STAGE_ARTIFACT:robustness:MC_RUNS' in result['errors']

def test_synthetic_full_chain_proves_wiring_but_never_paper_ready(tmp_path):
 m=json.loads(M.read_text()); c=new_chain(M,'control','h','XAUUSD','synthetic_control'); ids=['fixture']
 for stage in m['stages']:
  holdout=stage in {'python_translation','parity','paper'}
  c=append_receipt(c,m,stage,artifact(tmp_path,stage+'.json',pass_payload(stage,'control',ids,holdout,'synthetic_control')),
   'PASS',ids,holdout_accessed=holdout,
   translation_exact=True if stage=='python_translation' else None,
   parity_pass=True if stage=='parity' else None)
 result=verify(c,M)
 assert result['valid'] and result['operational_control_complete']
 assert result['control_only'] and not result['paper_ready'] and not result['promotable']
