#!/usr/bin/env python3
"""Read-only SXR8 contract probe. It cannot place or preview orders."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from packages.brokerage.ibkr_readonly import IbkrReadonlyClient

TARGET={"symbol":"SXR8","isin":"IE00B5BMR087","currency":"EUR","exchange_hint":"IBIS2"}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base-url',default='https://localhost:5000');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();client=IbkrReadonlyClient(a.base_url)
 try:auth=client.auth_status();error=None
 except Exception as exc:auth={"authenticated":False,"connected":False,"competing":False};error=f"{type(exc).__name__}: {exc}"
 report={"schema_version":1,"observed_at":dt.datetime.now(dt.timezone.utc).isoformat(),"target":TARGET,"auth":auth,"read_only":True,"orders_supported":False,"decision":"BLOCKED_GATEWAY_UNAVAILABLE" if error else "BLOCKED_NOT_AUTHENTICATED","error":error,"candidates":[]}
 if auth['authenticated'] and auth['connected']:
  for candidate in client.search(TARGET['symbol']):
   info=client.contract_info(candidate.conid)
   report['candidates'].append({"conid":candidate.conid,"symbol":candidate.symbol,"description":candidate.description,"sections":candidate.sections,"contracts":info})
  encoded=json.dumps(report['candidates'],sort_keys=True).encode();report['evidence_sha256']=hashlib.sha256(encoded).hexdigest();report['decision']='REVIEW_ACCOUNT_CONTRACT_RESULTS' if report['candidates'] else 'FAIL_NO_CONTRACT'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
