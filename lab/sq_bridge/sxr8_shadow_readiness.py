#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
def load(p):return json.loads(p.read_text())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--contract',type=Path,required=True);ap.add_argument('--research',type=Path,required=True);ap.add_argument('--schedule',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();contract,research,schedule=map(load,(a.contract,a.research,a.schedule));listing=research.get('decision',{}).get('by_listing',{}).get('SXR8_DE',{});stress=research.get('listings',{}).get('SXR8_DE',{}).get('cost_1000_eur',{}).get('slippage_10bps',{});actions=schedule.get('actions',[]);checks={
 'public_contract':contract.get('conid')==75776072 and contract.get('isin')=='IE00B5BMR087' and contract.get('exchange')=='IBIS2',
 'validation_oos_pass':listing.get('pass') is True,
 'stress_cost_positive':stress.get('total_return',-1)>0 and stress.get('profit_factor',0)>=1.25,
 'future_official_calendar':schedule.get('year')==2026 and schedule.get('sessions')==254 and len(actions)==22,
 'idempotent_schedule':len({x.get('idempotency_key') for x in actions})==len(actions),
 'orders_disabled':contract.get('paper_authorized') is False and contract.get('live_authorized') is False,
 'research_holdout_sealed':research.get('holdout_2025_accessed') is False,
 }
 ready=all(checks.values());report={'schema_version':1,'decision':'SHADOW_PAPER_READY' if ready else 'SHADOW_PAPER_BLOCKED','checks':checks,'missing':[k for k,v in checks.items() if not v],'broker_account_required':False,'orders_sent':0,'ibkr_paper_authorized':False,'live_authorized':False,'next_action':next((x for x in actions if x['date']>='2026-08-14'),None),'inputs_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.contract,a.research,a.schedule)}};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
