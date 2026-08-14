#!/usr/bin/env python3
"""Combine public contract, account probe, research and calendar evidence."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
def load(p):return json.loads(p.read_text())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--public-contract',type=Path,required=True);ap.add_argument('--account-probe',type=Path,required=True);ap.add_argument('--research',type=Path,required=True);ap.add_argument('--calendar',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();pub,probe,res,cal=map(load,(a.public_contract,a.account_probe,a.research,a.calendar));checks={
 'public_contract':pub.get('conid')==75776072 and pub.get('isin')=='IE00B5BMR087' and pub.get('exchange')=='IBIS2',
 'account_authenticated':probe.get('auth',{}).get('authenticated') is True and probe.get('auth',{}).get('connected') is True,
 'account_contract_match':any(c.get('conid')==75776072 for c in probe.get('candidates',[])),
 'research_listing_pass':res.get('decision',{}).get('by_listing',{}).get('SXR8_DE',{}).get('pass') is True,
 'calendar_deterministic':len(cal.get('actions',[]))>100 and len({x['idempotency_key'] for x in cal.get('actions',[])})==len(cal.get('actions',[])),
 'holdout_sealed':res.get('holdout_2025_accessed') is False,
 'observed_commission':probe.get('observed_commission_verified') is True,
 'fractional_or_whole_share_sizing':probe.get('sizing_verified') is True,
 }
 report={'schema_version':1,'decision':'PAPER_READY' if all(checks.values()) else 'PAPER_BLOCKED','checks':checks,'missing':[k for k,v in checks.items() if not v],'paper_authorized':all(checks.values()),'live_authorized':False,'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.public_contract,a.account_probe,a.research,a.calendar)}};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
