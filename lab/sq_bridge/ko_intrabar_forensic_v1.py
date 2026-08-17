#!/usr/bin/env python3
"""Resolve the sole KO same-D1 entry/PT ambiguity from frozen Dukascopy M1."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json
from datetime import datetime,timezone
from pathlib import Path

EXPECTED_M1='d69ceddcc06d8553bd264f23b68f6eb277e5a144b6421bcda2c11878bdbe74ea'
ENTRY_TS=1669818600;SESSION_END=1669842000;ENTRY=61.996;TARGET=63.457
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(path):
 if sha(path)!=EXPECTED_M1:raise ValueError('frozen KO M1 hash mismatch')
 with gzip.open(path,'rt',newline='') as f:rows=[r for r in csv.DictReader(f) if ENTRY_TS<=int(r['ts'])<SESSION_END]
 if len(rows)!=390 or int(rows[0]['ts'])!=ENTRY_TS or float(rows[0]['open'])!=ENTRY:raise ValueError('KO RTH/entry contract mismatch')
 first=None
 for r in rows:
  envelope=max(float(r[k]) for k in ('open','high','close'))
  if envelope>=TARGET:first=r;break
 if first is None:decision='REJECT_TARGET_NOT_OBSERVED'
 elif int(first['ts'])>ENTRY_TS:decision='PASS_ENTRY_PRECEDES_TARGET'
 else:decision='REJECT_ORDERING_NOT_RESOLVED'
 return {'schema_version':1,'decision':decision,'audit_kind':'post_hoc_execution_forensic_explicitly_allowed_by_parent_rejection','source_sha256':sha(path),'date':'2022-11-30','rth_minutes':len(rows),'entry':{'timestamp_utc':datetime.fromtimestamp(ENTRY_TS,timezone.utc).isoformat(),'price':ENTRY},'target':{'price':TARGET,'first_observed_minute_utc':datetime.fromtimestamp(int(first['ts']),timezone.utc).isoformat() if first else None,'minutes_after_entry':(int(first['ts'])-ENTRY_TS)//60 if first else None,'canonical_envelope':max(float(first[k]) for k in ('open','high','close')) if first else None},'envelope_rule':'max(open,high,close), matching the canonical repair of known raw Dukascopy high-envelope quirks','oos_2024_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('m1',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=run(a.m1);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
