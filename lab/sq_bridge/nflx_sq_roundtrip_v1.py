#!/usr/bin/env python3
"""Prove SQ preserves every NFLX D1 date and OHLC value."""
import argparse,csv,hashlib,json
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
 with p.open(newline='') as s:return [[x for x in r] for r in csv.reader(s)]
def audit(source,export):
 a,b=load(source),load(export);mismatches=[]
 for i,(x,y) in enumerate(zip(a,b)):
  if x[:2]!=y[:2] or any(abs(float(x[j])-float(y[j]))>0.0000005 for j in range(2,6)):mismatches.append(i)
 passed=len(a)==len(b)==1995 and not mismatches
 return {'schema_version':1,'decision':'PASS_NFLX_SQ_D1_ROUNDTRIP' if passed else 'FAIL_NFLX_SQ_D1_ROUNDTRIP','source_rows':len(a),'export_rows':len(b),'date_ohlc_mismatches':len(mismatches),'source_sha256':sha(source),'sq_export_sha256':sha(export),'volume_parity_required':False,'volume_rules_allowed':False,'performance_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--export',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.source,a.export);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
