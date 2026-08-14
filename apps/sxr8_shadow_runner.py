#!/usr/bin/env python3
"""Create a hypothetical SXR8 intent from a precomputed exchange calendar."""
from __future__ import annotations
import argparse,datetime as dt,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from packages.execution.shadow import ShadowIntent,append_once,hypothetical_position,load_ledger,sync_csv,whole_share_size

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--calendar',type=Path,required=True);ap.add_argument('--ledger',type=Path,required=True);ap.add_argument('--session',type=dt.date.fromisoformat,required=True);ap.add_argument('--reference-price',type=float,required=True);ap.add_argument('--capital',type=float,default=1000);ap.add_argument('--commission',type=float,default=1.25);ap.add_argument('--reserve-pct',type=float,default=.05);a=ap.parse_args();cal=json.loads(a.calendar.read_text());matches=[x for x in cal['actions'] if x['date']==a.session.isoformat()]
 report={"schema_version":1,"session":a.session.isoformat(),"mode":"shadow","orders_sent":0,"action":"NONE","created":False}
 if matches:
  action=matches[0];position=hypothetical_position(load_ledger(a.ledger),'SXR8');qty=whole_share_size(a.capital,a.reference_price,a.commission,a.reserve_pct) if action['action']=='BUY' else position
  if action['action']=='BUY' and qty==0:report.update(action='BLOCKED_INSUFFICIENT_CAPITAL',reason='whole_share_size_zero')
  elif action['action']=='BUY' and position:report.update(action='BLOCKED_POSITION_ALREADY_OPEN',reason=f'hypothetical_position={position}')
  elif action['action']=='SELL' and qty==0:report.update(action='BLOCKED_NO_POSITION',reason='hypothetical_position_zero')
  else:
   intent=ShadowIntent(action['idempotency_key'],'sxr8_turn_of_month','SXR8',action['action'],a.session.isoformat(),a.reference_price,qty,qty*a.reference_price,a.commission);report.update(action=action['action'],created=append_once(a.ledger,intent),intent=intent.__dict__,hypothetical_position_before=position)
 sync_csv(a.ledger);report['csv_ledger']=str(a.ledger.with_suffix('.csv'));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
