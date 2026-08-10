from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.test_evidence_chain import M, pass_payload
import json


def test_small_account_requires_exact_canonical_capital_and_leverage_grid():
 methodology=json.loads(M.read_text()); artifact=pass_payload('small_account_economics','c',['a'])
 receipt={"decision":"PASS","candidate_ids":["a"],"holdout_accessed":False}
 assert validate_stage_artifact('small_account_economics',artifact,receipt,methodology,'c','alquimia_native')==[]
 artifact['capital_usdc']=1000; artifact['selected_leverage']=7
 errors=validate_stage_artifact('small_account_economics',artifact,receipt,methodology,'c','alquimia_native')
 assert 'STAGE_ARTIFACT:small_account_economics:CAPITAL' in errors
 assert 'STAGE_ARTIFACT:small_account_economics:LEVERAGE' in errors


def test_parity_requires_exact_signal_and_trade_matching():
 methodology=json.loads(M.read_text()); artifact=pass_payload('parity','c',['a'],True)
 receipt={"decision":"PASS","candidate_ids":["a"],"holdout_accessed":True,"parity_pass":True}
 artifact['signal_match_rate']=.999
 errors=validate_stage_artifact('parity',artifact,receipt,methodology,'c','alquimia_native')
 assert 'STAGE_ARTIFACT:parity:SIGNALS' in errors


def test_malformed_candidate_ids_are_rejected_without_crashing():
 methodology=json.loads(M.read_text()); artifact=pass_payload('market_preflight','c',[])
 receipt={"decision":"PASS","candidate_ids":[],"holdout_accessed":False}
 artifact['candidate_ids']=None
 errors=validate_stage_artifact('market_preflight',artifact,receipt,methodology,'c','alquimia_native')
 assert 'STAGE_ARTIFACT:market_preflight:CANDIDATES' in errors
