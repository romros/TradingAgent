#!/usr/bin/env python3
"""Advance frozen NFLX 0.4681 through completed forward sessions; shadow only."""
from __future__ import annotations
import argparse,csv,json,math,os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.execution.shadow import ShadowIntent,append_many_once,ensure_ledger
from packages.strategy.nflx_04681 import bracket,exit_on_bar,new_pending,pending_for_next
def atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,prefix='.'+path.name) as f:t=Path(f.name);json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 t.replace(path)
def load_rows(path):
 with path.open(newline='',encoding='utf-8-sig') as f:r=list(csv.DictReader(f))
 r.sort(key=lambda x:x['date'])
 if len(r)<105 or len({x['date'] for x in r})!=len(r):raise ValueError('NFLX feed needs >=105 unique sessions')
 return r
def quantity(capital,exposure,price):return max(0,math.floor(capital*exposure/(price*1.001+1)))
def main():
 p=argparse.ArgumentParser();p.add_argument('--candles',type=Path,required=True);p.add_argument('--ledger',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--capital',type=float,default=3000);p.add_argument('--exposure',type=float,default=.75);a=p.parse_args()
 rows=load_rows(a.candles);ensure_ledger(a.ledger)
 if not a.state.exists():
  state={'schema_version':1,'mode':'shadow','strategy':'nflx_04681','last_session':rows[-1]['date'],'pending':pending_for_next(rows),'position':None,'bootstrap':'NO_RETROACTIVE_INTENTS','orders_sent':0,'paper_authorized':False,'live_authorized':False};atomic(a.state,state);print(json.dumps({'status':'PASS_BOOTSTRAP','action':'INITIALIZED_FOR_NEXT_SESSION','state':state,'orders_sent':0},indent=2));return
 state=json.loads(a.state.read_text());last=state['last_session'];indexes=[i for i,r in enumerate(rows) if r['date']>last];actions=[]
 for i in indexes:
  row=rows[i];day=row['date'];position=state.get('position');exited_at_open=False;exited_intraday=False
  intents=[]
  if position:
   hit=exit_on_bar(row,float(position['stop']),float(position['target']))
   if hit:
    kind,price,exited_at_open=hit;exited_intraday=not exited_at_open
    intents.append(ShadowIntent(f'nflx_04681:{day}:SELL:{kind}','nflx_04681','NFLX','SELL',day,price,int(position['quantity']),price*int(position['quantity']),1.0,metadata={'exit_type':kind,'stop':position['stop'],'target':position['target'],'frozen_rule':'NFLX SQ 0.4681'}));state['position']=None
  if not state.get('position') and not exited_intraday:
   pending=state.get('pending')
   if pending:
    pending['age']=int(pending.get('age',0))+1
    if pending['age']>=80:pending=None
   entry=None;base=None;distance=None
   if pending and float(row['open'])>=float(pending['price']):entry=float(row['open']);base=float(pending['price']);distance=float(pending['atr15']);pending=None
   if entry is None:
    pending=new_pending(rows,i)
    if pending and float(pending['price'])<float(row['open']):pending=None
    elif pending and float(row['high'])>=float(pending['price']):entry=base=float(pending['price']);distance=float(pending['atr15']);pending=None
   state['pending']=pending
   if entry is not None:
    q=quantity(a.capital,a.exposure,entry);stop,target=bracket(base,distance)
    if q<1:actions.append({'session':day,'action':'BLOCKED_INSUFFICIENT_CAPITAL'})
    else:
     intents.append(ShadowIntent(f'nflx_04681:{day}:BUY','nflx_04681','NFLX','BUY',day,entry,q,entry*q,1.0,metadata={'stop':stop,'target':target,'entry_stop_base':base,'exposure_fraction':a.exposure,'frozen_rule':'NFLX SQ 0.4681'}));state['position']={'entry_session':day,'entry':entry,'quantity':q,'stop':stop,'target':target,'entry_stop_base':base}
     hit=exit_on_bar(row,stop,target)
     if hit:
      kind,price,_=hit;intents.append(ShadowIntent(f'nflx_04681:{day}:SELL:{kind}','nflx_04681','NFLX','SELL',day,price,q,price*q,1.0,metadata={'exit_type':kind,'stop':stop,'target':target,'frozen_rule':'NFLX SQ 0.4681'}));state['position']=None
  created=append_many_once(a.ledger,intents) if intents else 0;actions.append({'session':day,'action':' / '.join(x.action for x in intents) or 'NONE','intents_created':created});state['last_session']=day
 atomic(a.state,state);print(json.dumps({'status':'PASS','action':actions[-1]['action'] if actions else 'NO_NEW_COMPLETED_SESSION','processed':actions,'state':state,'orders_sent':0},indent=2))
if __name__=='__main__':main()
