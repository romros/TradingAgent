#!/usr/bin/env python3
"""Marginal portfolio test of the unchanged GOOG Momentum60 rule."""
from __future__ import annotations
import argparse,csv,json,math
from bisect import bisect_right
from datetime import date
from pathlib import Path
from lab.sq_bridge.four_edge_position_leverage_audit_v2 import audit,sha
from lab.sq_bridge.five_edge_daily_mtm_v1 import drawdown

EXPECTED='08832095461d69dd4958c8c53be30eee4b0eb2e53943ff9c799b4f40a654781a';CAPITAL=2000.;LIMIT=2000.;CAP=500.;RATE=.08;SLIP=.00125
START,END=date(2022,1,1),date(2024,12,31)
def load(path):
 out=[]
 with path.open(newline='') as f:
  for r in csv.DictReader(f):
   d=date.fromisoformat(r['date'])
   if START<=d<=END:out.append((d,float(r['open']),float(r['close'])))
 return out
def planned(rows):
 out=[]
 for i in range(61,len(rows)-20):
  if rows[i][0].month!=rows[i-1][0].month and rows[i-1][2]>rows[i-61][2]:out.append((i,i+20))
 return out
def prior(days,vals,d):
 i=bisect_right(days,d)-1;return vals[i] if i>=0 else vals[0]
def evaluate(sqx,fx,orders,goog):
 if sha(goog)!=EXPECTED:raise ValueError('frozen GOOG source mismatch')
 b=audit(sqx,fx,orders,include_daily=True)['scenarios']['stress'];be={date.fromisoformat(x['date']):x['equity_usd'] for x in b.pop('daily_equity')};bc={date.fromisoformat(x['date']):x['cash_usd'] for x in b.pop('daily_cash')};bd=sorted(be);bv=[be[x] for x in bd];cd=sorted(bc);cv=[bc[x] for x in cd]
 rows=load(goog);index={x[0]:i for i,x in enumerate(rows)};entries={rows[a][0]:(a,z) for a,z in planned(rows)};exits={rows[z][0]:(a,z) for a,z in planned(rows)}
 days=sorted(set(bd)|set(index));cash=0.;pos=None;trades=[];skip_margin=0;fin=0.;combined=[];prev=days[0]
 for d in days:
  active=prior(cd,cv,d);extra=max(-(active+cash),0)-max(-active,0);charge=max(extra,0)*RATE*(d-prev).days/365.2425;cash-=charge;fin+=charge
  if pos is not None and d==pos['exit']:
   price=rows[index[d]][1]*(1-SLIP);proceeds=pos['shares']*price-1;cash+=proceeds;trades.append(proceeds-pos['cost']);pos=None
  if pos is None and d in entries:
   i,z=entries[d];price=rows[i][1]*(1+SLIP);shares=math.floor((CAP-1)/price);cost=shares*price+1
   if shares and active+cash-cost>=-LIMIT:cash-=cost;pos={'shares':shares,'cost':cost,'exit':rows[z][0]}
   elif shares:skip_margin+=1
  value=cash+(pos['shares']*rows[index[d]][2] if pos and d in index else 0);combined.append((d,prior(bd,bv,d)+value));prev=d
 maximum,pair=drawdown(combined);final=combined[-1][1];years=(END-START).days/365.2425;cagr=((final/CAPITAL)**(1/years)-1)*100;wins=sum(max(x,0) for x in trades);loss=sum(max(-x,0) for x in trades);passed=cagr>15.99959 and maximum<=20 and min(v for _,v in combined)>0
 return {'schema_version':1,'decision':'PASS_ADMIT_GOOG_MOMENTUM60_MARGINAL' if passed else 'FAIL_GOOG_MOMENTUM60_MARGINAL','period':f'{START}/{END}','initial_capital_usd':CAPITAL,'final_equity_usd':round(final,6),'net_return_pct':round((final/CAPITAL-1)*100,6),'cagr_pct':round(cagr,6),'daily_mtm_max_drawdown_pct':round(maximum,6),'drawdown_peak_date':str(pair[0]),'drawdown_trough_date':str(pair[1]),'minimum_equity_usd':round(min(v for _,v in combined),6),'candidate':{'trades':len(trades),'profit_factor':round(wins/loss,6) if loss else None,'net_pnl_before_financing_usd':round(sum(trades),6),'extra_financing_usd':round(fin,6),'skipped_margin':skip_margin,'open_position_at_boundary':pos is not None},'base':{'return_pct':56.041808,'cagr_pct':15.99959,'drawdown_pct':15.915973},'recent_external_confirmation':{'return_pct':10.0441,'profit_factor':1.305338,'drawdown_pct':26.3400,'standalone_gate_passed':False},'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('sqx',type=Path);p.add_argument('--fx',type=Path,required=True);p.add_argument('--goog',type=Path,required=True)
 for k in ('cat','msft','jpm','sgln'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=evaluate(a.sqx,a.fx,{k:getattr(a,k) for k in ('cat','msft','jpm','sgln')},a.goog);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
