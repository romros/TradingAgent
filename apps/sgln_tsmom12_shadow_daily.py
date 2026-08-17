#!/usr/bin/env python3
"""Stateful SGLN TSMOM12 shadow with observed GBPUSD conversion."""
from __future__ import annotations
import argparse,bisect,csv,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.nflx_04681_shadow_daily import atomic
from packages.execution.shadow import ShadowIntent,append_many_once
from packages.strategy.sgln_tsmom12 import desired_long
def main():
 p=argparse.ArgumentParser();p.add_argument('--candles',type=Path,required=True);p.add_argument('--fx',type=Path,required=True);p.add_argument('--ledger',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--capital',type=float,default=500);a=p.parse_args();rows=list(csv.DictReader(a.candles.open()));fxrows=list(csv.DictReader(a.fx.open()));fxdays=[r['date'] for r in fxrows];fxvals=[float(r['close']) for r in fxrows]
 def rate(day):
  i=bisect.bisect_right(fxdays,day)-1
  if i<0:raise ValueError(f'missing GBPUSD before {day}')
  return fxvals[i]
 state=json.loads(a.state.read_text()) if a.state.exists() else None
 if len(rows)<260:raise ValueError('SGLN requires at least 12 calendar months')
 if state is None:
  state={'schema_version':1,'mode':'shadow','strategy':'sgln_tsmom12','last_session':rows[-1]['date'],'position':None,'cash_usd':a.capital,'bootstrap':'NO_RETROACTIVE_INTENTS','orders_sent':0,'paper_authorized':False,'live_authorized':False};atomic(a.state,state);print(json.dumps({'status':'PASS_BOOTSTRAP','action':'INITIALIZED_FOR_NEXT_MONTH','state':state,'orders_sent':0},indent=2));return
 dates=[r['date'] for r in rows];start=dates.index(state['last_session'])+1 if state.get('last_session') in dates else len(rows);intents=[];processed=[]
 for i in range(start,len(rows)):
  r=rows[i];day=r['date'];desired=desired_long(rows,i)
  if desired is not None:
   fx=rate(day);open_gbp=float(r['open'])/100
   if desired and state.get('position') is None:
    fee=3*fx;price_usd=open_gbp*fx*1.002;q=math.floor((state['cash_usd']-fee)/price_usd)
    if q>=1:
     state['cash_usd']-=q*price_usd+fee;state['position']={'entry_session':day,'quantity':q,'entry_price_usd':price_usd,'entry_fx':fx};intents.append(ShadowIntent(f'sgln_tsmom12:{day}:BUY','sgln_tsmom12','SGLN','BUY',day,price_usd,q,price_usd*q,fee,metadata={'fx_gbpusd':fx,'raw_open_gbp':open_gbp,'frozen_rule':'SGLN exact-month TSMOM12'}))
   elif not desired and state.get('position'):
    q=int(state['position']['quantity']);fee=3*fx;price_usd=open_gbp*fx*.998;state['cash_usd']+=q*price_usd-fee;intents.append(ShadowIntent(f'sgln_tsmom12:{state["position"]["entry_session"]}:SELL','sgln_tsmom12','SGLN','SELL',day,price_usd,q,price_usd*q,fee,metadata={'fx_gbpusd':fx,'raw_open_gbp':open_gbp,'exit_type':'TSMOM_FALSE','frozen_rule':'SGLN exact-month TSMOM12'}));state['position']=None
  state['last_session']=day;processed.append(day)
 created=append_many_once(a.ledger,intents);atomic(a.state,state);print(json.dumps({'status':'PASS','action':'INTENTS_CREATED' if created else 'NONE','processed':processed,'created':created,'state':state,'orders_sent':0},indent=2))
if __name__=='__main__':main()
