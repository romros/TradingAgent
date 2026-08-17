#!/usr/bin/env python3
"""Stateful, forward-only JPM Momentum60 shadow executor."""
from __future__ import annotations
import argparse,csv,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.nflx_04681_shadow_daily import atomic
from packages.execution.shadow import ShadowIntent,append_many_once
from packages.strategy.jpm_momentum60 import entry_on,exit_on
def main():
 p=argparse.ArgumentParser();p.add_argument('--candles',type=Path,required=True);p.add_argument('--ledger',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--capital',type=float,default=500);a=p.parse_args();rows=list(csv.DictReader(a.candles.open()));state=json.loads(a.state.read_text()) if a.state.exists() else None
 if len(rows)<62:raise ValueError('JPM requires at least 62 completed sessions')
 if state is None:
  state={'schema_version':1,'mode':'shadow','strategy':'jpm_momentum60','last_session':rows[-1]['date'],'position':None,'realized_equity':a.capital,'bootstrap':'NO_RETROACTIVE_INTENTS','orders_sent':0,'paper_authorized':False,'live_authorized':False};atomic(a.state,state);print(json.dumps({'status':'PASS_BOOTSTRAP','action':'INITIALIZED_FOR_NEXT_SESSION','state':state,'orders_sent':0},indent=2));return
 dates=[r['date'] for r in rows];start=dates.index(state['last_session'])+1 if state.get('last_session') in dates else len(rows);intents=[];processed=[]
 for i in range(start,len(rows)):
  r=rows[i];day=r['date'];position=state.get('position')
  if position and exit_on(rows,i,position['entry_session']):
   q=int(position['quantity']);price=float(r['open'])*.999;fee=max(1,.005*q);pnl=q*(price-position['entry_price'])-fee;state['realized_equity']+=q*price-fee;intents.append(ShadowIntent(f'jpm_momentum60:{position["entry_session"]}:SELL','jpm_momentum60','JPM','SELL',day,price,q,price*q,fee,metadata={'exit_type':'HOLD_20_OPEN','pnl_usd':pnl,'frozen_rule':'JPM Momentum60 month-end'}));state['position']=None
  if state.get('position') is None and entry_on(rows,i):
   price=float(r['open'])*1.001;fee=1.;q=math.floor((state['realized_equity']-fee)/price)
   if q>=1:
    state['realized_equity']-=q*price+max(1,.005*q);state['position']={'entry_session':day,'entry_price':price,'quantity':q};intents.append(ShadowIntent(f'jpm_momentum60:{day}:BUY','jpm_momentum60','JPM','BUY',day,price,q,price*q,max(1,.005*q),metadata={'exit_after_bars':20,'frozen_rule':'JPM Momentum60 month-end'}))
  state['last_session']=day;processed.append(day)
 created=append_many_once(a.ledger,intents);atomic(a.state,state);print(json.dumps({'status':'PASS','action':'INTENTS_CREATED' if created else 'NONE','processed':processed,'created':created,'state':state,'orders_sent':0},indent=2))
if __name__=='__main__':main()
