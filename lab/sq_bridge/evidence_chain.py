#!/usr/bin/env python3
"""Immutable stage receipts and promotion verifier for Alquimia v3."""
from __future__ import annotations
import argparse, hashlib, json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact

DECISIONS={"PASS","REJECT","BLOCK"}

def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha_bytes(value): return hashlib.sha256(value).hexdigest()
def sha_file(path): return sha_bytes(Path(path).read_bytes())
def normalized_ids(value):
 return sorted(set(value)) if isinstance(value,list) and all(isinstance(item,str) and item for item in value) else []

def new_chain(methodology_path, campaign_id, hypothesis_id, market, provenance="alquimia_native"):
 mpath=Path(methodology_path); m=json.loads(mpath.read_text())
 return {"schema_version":2,"campaign_id":campaign_id,"hypothesis_id":hypothesis_id,"market":market,
  "capital_usdc":m["capital_usdc"],"methodology_id":m["methodology_id"],
  "methodology_sha256":sha_file(mpath),"provenance":provenance,
  "legacy_quantitative_inputs":[],"receipts":[],"live_authorized":False}

def append_receipt(chain,methodology,stage,artifact,decision,candidate_ids=(),holdout_accessed=False,translation_exact=None,parity_pass=None):
 out=deepcopy(chain); stages=methodology["stages"]
 if stage not in stages: raise ValueError("UNKNOWN_STAGE")
 expected=stages[len(out["receipts"])] if len(out["receipts"])<len(stages) else None
 if stage!=expected: raise ValueError(f"STAGE_ORDER expected={expected} got={stage}")
 if decision not in DECISIONS: raise ValueError("INVALID_DECISION")
 if out["receipts"] and out["receipts"][-1]["decision"]!="PASS": raise ValueError("TERMINAL_CHAIN")
 previous=out["receipts"][-1]["candidate_ids"] if out["receipts"] else []
 ids=sorted(set(candidate_ids))
 if previous and not set(ids).issubset(previous): raise ValueError("CANDIDATE_LINEAGE_VIOLATION")
 path=Path(artifact)
 receipt={"stage":stage,"decision":decision,"artifact":str(path),"artifact_sha256":sha_file(path),
  "candidate_ids":ids,"holdout_accessed":bool(holdout_accessed),
  "translation_exact":translation_exact,"parity_pass":parity_pass,
  "previous_receipt_sha256":out["receipts"][-1]["receipt_sha256"] if out["receipts"] else None}
 receipt["receipt_sha256"]=sha_bytes(canonical(receipt))
 out["receipts"].append(receipt); return out

def verify(chain,methodology_path):
 errors=[]; warnings=[]; mpath=Path(methodology_path); m=json.loads(mpath.read_text()); stages=m["stages"]
 if chain.get("methodology_sha256")!=sha_file(mpath): errors.append("METHODOLOGY_HASH_MISMATCH")
 if chain.get("capital_usdc")!=200 or m.get("capital_usdc")!=200: errors.append("CAPITAL_NOT_200")
 if chain.get("live_authorized") is not False: errors.append("LIVE_MUST_REQUIRE_EXTERNAL_AUTHORIZATION")
 if chain.get("legacy_quantitative_inputs"): errors.append("LEGACY_QUANTITATIVE_INPUTS_FORBIDDEN")
 previous_ids=[]; previous_hash=None; terminal=False; screened_hypotheses=[]
 robustness_metrics={}
 for i,r in enumerate(chain.get("receipts",[])):
  if i>=len(stages) or r.get("stage")!=stages[i]: errors.append(f"STAGE_ORDER:{i}")
  if terminal: errors.append(f"RECEIPT_AFTER_TERMINAL:{r.get('stage')}")
  if r.get("decision") not in DECISIONS: errors.append(f"INVALID_DECISION:{i}")
  path=Path(r.get("artifact",""))
  if not path.is_file() or r.get("artifact_sha256")!=(sha_file(path) if path.is_file() else None): errors.append(f"ARTIFACT_HASH:{i}")
  if chain.get("schema_version",1)>=2 and path.is_file():
   try:
    artifact=json.loads(path.read_text())
    if not isinstance(artifact,dict): raise ValueError("not object")
   except Exception: errors.append(f"STAGE_ARTIFACT:{r.get('stage')}:NOT_JSON_OBJECT")
   else:
    errors.extend(validate_stage_artifact(r.get("stage"),artifact,r,m,chain.get("campaign_id"),chain.get("provenance")))
    if r.get("stage")=="hypothesis_screen" and r.get("decision")=="PASS":
     screened_hypotheses=normalized_ids(artifact.get("selected_hypothesis_ids"))
    if r.get("stage")=="sq_generation" and r.get("decision")=="PASS":
     source_hypotheses=normalized_ids(artifact.get("source_hypothesis_ids"))
     if not screened_hypotheses or not set(source_hypotheses).issubset(screened_hypotheses):
      errors.append("SQ_HYPOTHESIS_LINEAGE")
    if (m.get("schema_version",1)>=4
        and r.get("stage")=="temporal_validation" and r.get("decision")=="PASS"):
     evaluated=artifact.get("evaluated_candidate_temporal_metrics")
     if not isinstance(evaluated,dict) or set(evaluated)!=set(previous_ids):
      errors.append("TEMPORAL_EVALUATED_LINEAGE")
    if (m.get("schema_version",1)>=4
        and r.get("stage")=="robustness" and r.get("decision")=="PASS"):
     evaluated=artifact.get("evaluated_candidate_robustness_metrics")
     if not isinstance(evaluated,dict) or set(evaluated)!=set(previous_ids):
      errors.append("ROBUSTNESS_EVALUATED_LINEAGE")
     else: robustness_metrics=evaluated
    if (m.get("schema_version",1)>=4
        and r.get("stage")=="small_account_economics" and r.get("decision")=="PASS"):
     candidate_ids=normalized_ids(r.get("candidate_ids"))
     metric=robustness_metrics.get(candidate_ids[0]) if len(candidate_ids)==1 else None
     selected_leverage=artifact.get("selected_leverage")
     selected_venue_max=artifact.get("venue_max_leverage")
     tested_leverage=metric.get("tested_leverage") if isinstance(metric,dict) else None
     tested_venue_max=metric.get("venue_max_leverage") if isinstance(metric,dict) else None
     if (not isinstance(selected_leverage,(int,float)) or isinstance(selected_leverage,bool)
         or not isinstance(tested_leverage,(int,float)) or isinstance(tested_leverage,bool)
         or selected_leverage>tested_leverage or selected_venue_max!=tested_venue_max):
      errors.append("SMALL_ACCOUNT_EXCEEDS_ROBUSTNESS_LEVERAGE")
    if (m.get("schema_version",1)>=4 and chain.get("provenance")!="synthetic_control"
        and r.get("stage")=="paper"
        and r.get("decision")=="PASS"):
     try:
      config_path=Path(artifact["paper_config_path"])
      config_path=config_path if config_path.is_absolute() else path.resolve().parent/config_path
      config=json.loads(config_path.read_text())
      refs=config["source_artifacts"]
      prior={item["stage"]:item["artifact_sha256"] for item in chain["receipts"][:i]}
      roles=("market_preflight","small_account_economics","final_holdout_validation",
             "python_translation","parity")
      if any(refs[role]["sha256"]!=prior.get(role) for role in roles):
       errors.append("PAPER_SOURCE_RECEIPT_LINEAGE")
     except (KeyError,OSError,TypeError,ValueError,json.JSONDecodeError):
      errors.append("PAPER_SOURCE_RECEIPT_LINEAGE")
  check=dict(r); stored=check.pop("receipt_sha256",None)
  if stored!=sha_bytes(canonical(check)): errors.append(f"RECEIPT_HASH:{i}")
  if r.get("previous_receipt_sha256")!=previous_hash: errors.append(f"CHAIN_LINK:{i}")
  ids=r.get("candidate_ids",[])
  if previous_ids and not set(ids).issubset(previous_ids): errors.append(f"CANDIDATE_LINEAGE:{i}")
  if r.get("holdout_accessed") and i<stages.index("small_account_economics")+1: errors.append(f"EARLY_HOLDOUT:{i}")
  if m.get("schema_version",1)>=4:
   expected_holdout=r.get("stage")=="final_holdout_validation"
   if bool(r.get("holdout_accessed")) is not expected_holdout:
    errors.append(f"HOLDOUT_STAGE_CONTRACT:{i}")
  if r.get("stage")=="python_translation" and r.get("decision")=="PASS" and r.get("translation_exact") is not True: errors.append("TRANSLATION_NOT_EXACT")
  if r.get("stage")=="parity" and r.get("decision")=="PASS" and r.get("parity_pass") is not True: errors.append("PARITY_NOT_PASS")
  previous_ids=ids; previous_hash=stored; terminal=r.get("decision") in {"REJECT","BLOCK"}
 if chain.get("schema_version",1)<2: warnings.append("LEGACY_CHAIN_WITHOUT_STRICT_STAGE_ARTIFACT_CONTRACT")
 if chain.get("provenance")=="legacy_example" and chain.get("receipts") and chain["receipts"][-1]["decision"]=="PASS": errors.append("LEGACY_EXAMPLE_CANNOT_PROMOTE")
 receipts=chain.get("receipts",[]); next_stage=None if terminal or len(receipts)>=len(stages) else stages[len(receipts)]
 promotable=bool(receipts) and not errors and receipts[-1]["decision"]=="PASS" and next_stage is not None
 control_only=chain.get("provenance")=="synthetic_control"
 operational_control_complete=control_only and not errors and len(receipts)==len(stages) and all(r["decision"]=="PASS" for r in receipts)
 if control_only: promotable=False
 paper_ready=not control_only and not errors and len(receipts)==len(stages) and all(r["decision"]=="PASS" for r in receipts)
 return {"valid":not errors,"errors":errors,"warnings":warnings,"terminal":terminal,"next_stage":next_stage,"promotable":promotable,"paper_ready":paper_ready,"control_only":control_only,"operational_control_complete":operational_control_complete,"live_authorized":False}

def main():
 p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
 n=sub.add_parser("new"); n.add_argument("--methodology",type=Path,required=True); n.add_argument("--campaign",required=True); n.add_argument("--hypothesis",required=True); n.add_argument("--market",required=True); n.add_argument("--output",type=Path,required=True)
 a=sub.add_parser("append"); a.add_argument("chain",type=Path); a.add_argument("--methodology",type=Path,required=True); a.add_argument("--stage",required=True); a.add_argument("--artifact",type=Path,required=True); a.add_argument("--decision",choices=sorted(DECISIONS),required=True); a.add_argument("--candidate-id",action="append",default=[]); a.add_argument("--holdout-accessed",action="store_true"); a.add_argument("--translation-exact",action="store_true",default=None); a.add_argument("--parity-pass",action="store_true",default=None); a.add_argument("--output",type=Path,required=True)
 v=sub.add_parser("verify"); v.add_argument("chain",type=Path); v.add_argument("--methodology",type=Path,required=True)
 a=p.parse_args()
 if a.cmd=="new":
  result=new_chain(a.methodology,a.campaign,a.hypothesis,a.market)
  a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n")
 elif a.cmd=="append":
  if a.chain.resolve()==a.output.resolve(): raise SystemExit("CHAIN_INPUT_OUTPUT_MUST_DIFFER")
  methodology=json.loads(a.methodology.read_text())
  result=append_receipt(json.loads(a.chain.read_text()),methodology,a.stage,a.artifact,a.decision,a.candidate_id,a.holdout_accessed,a.translation_exact,a.parity_pass)
  a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n")
 else: result=verify(json.loads(a.chain.read_text()),a.methodology)
 print(json.dumps(result,indent=2)); raise SystemExit(0 if a.cmd in {"new","append"} or result["valid"] else 2)
if __name__=="__main__": main()
