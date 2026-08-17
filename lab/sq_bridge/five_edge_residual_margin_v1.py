#!/usr/bin/env python3
"""Test the consolidated multi-asset edge using only residual 2x margin."""
from __future__ import annotations
import argparse,json,math
from bisect import bisect_right
from datetime import date
from pathlib import Path
from lab.sq_bridge.four_edge_position_leverage_audit_v2 import audit
from lab.sq_bridge.multi_asset_known_edge_funnel_v1 import ROOT,load,sma
from lab.sq_bridge.five_edge_daily_mtm_v1 import drawdown

CAPITAL=2000.; BORROW_LIMIT=2000.; SLOT=333.33; RATE=.08
START,END=date(2022,1,1),date(2024,12,31)

def asof(days,values,day):
 i=bisect_right(days,day)-1
 return values[i] if i>=0 else values[0]

def evaluate(sqx,fx,orders,strategy_spec):
 base=audit(sqx,fx,orders,include_daily=True)['scenarios']['stress']
 base_eq={date.fromisoformat(x['date']):x['equity_usd'] for x in base.pop('daily_equity')}
 base_cash={date.fromisoformat(x['date']):x['cash_usd'] for x in base.pop('daily_cash')}
 base_days=sorted(base_eq);cash_days=sorted(base_cash);cash_values=[base_cash[d] for d in cash_days]
 spec=json.loads(strategy_spec.read_text());data={a:load(ROOT/p) for a,p in spec['assets'].items()}
 indexed={a:{date.fromisoformat(r['date']):i for i,r in enumerate(rows)} for a,rows in data.items()}
 days=sorted(set(base_days)|{date.fromisoformat(r['date']) for rows in data.values() for r in rows if '2022-01-01'<=r['date']<='2024-12-31'})
 positions={};addon_cash=0.;trades=[];skipped_margin=0;skipped_price=0;combined=[];extra_financing=0.;previous=days[0]
 for day in days:
  active_cash=asof(cash_days,cash_values,day)
  extra_borrow=max(-(active_cash+addon_cash),0)-max(-active_cash,0)
  charge=max(extra_borrow,0)*RATE*(day-previous).days/365.2425
  addon_cash-=charge;extra_financing+=charge
  # Exits occur before new entries.
  for asset,pos in list(positions.items()):
   idx=indexed[asset].get(day)
   if idx is not None and idx-pos['entry_index']>=10:
    price=data[asset][idx]['open']*.999;proceeds=pos['shares']*price-1.;addon_cash+=proceeds
    trades.append({'asset':asset,'entry':pos['entry_date'],'exit':day.isoformat(),'pnl_usd':proceeds-pos['cost']});del positions[asset]
  slots=3-len(positions);signals=[]
  if slots:
   for asset,rows in data.items():
    if asset in positions:continue
    idx=indexed[asset].get(day)
    if idx is None or idx<201:continue
    signal=idx-1;avg=sma(rows,signal,200)
    if avg is not None and rows[signal]['close']>avg and all(rows[j]['close']<rows[j-1]['close'] for j in range(signal-2,signal+1)):
     signals.append((rows[signal]['close']/rows[signal-3]['close']-1,asset,idx))
   for _,asset,idx in sorted(signals)[:slots]:
    price=data[asset][idx]['open']*1.001;shares=math.floor((SLOT-1.)/price)
    if shares<1:skipped_price+=1;continue
    cost=shares*price+1.
    if active_cash+addon_cash-cost < -BORROW_LIMIT:
     skipped_margin+=1;continue
    addon_cash-=cost;positions[asset]={'shares':shares,'cost':cost,'entry_date':day.isoformat(),'entry_index':idx}
  addon_equity=addon_cash
  for asset,pos in positions.items():
   idx=indexed[asset].get(day)
   price=data[asset][idx]['close'] if idx is not None else data[asset][pos['entry_index']]['open']
   addon_equity+=pos['shares']*price
  combined.append((day,asof(base_days,[base_eq[d] for d in base_days],day)+addon_equity));previous=day
 # Boundary-open positions are restored at entry cost, matching the frozen candidate convention.
 if positions:
  adjustment=sum(p['cost'] for p in positions.values())-sum(p['shares']*(data[a][indexed[a].get(END,p['entry_index'])]['close'] if END in indexed[a] else data[a][p['entry_index']]['open']) for a,p in positions.items())
  combined[-1]=(combined[-1][0],combined[-1][1]+adjustment)
 maximum,pair=drawdown(combined);final=combined[-1][1];years=(END-START).days/365.2425;cagr=((final/CAPITAL)**(1/years)-1)*100
 passed=cagr>15.99959 and maximum<=20 and min(v for _,v in combined)>0
 wins=sum(max(t['pnl_usd'],0) for t in trades);loss=sum(max(-t['pnl_usd'],0) for t in trades)
 return {'schema_version':1,'decision':'PASS_ADMIT_FIFTH_EDGE_RESIDUAL_MARGIN' if passed else 'FAIL_FIFTH_EDGE_RESIDUAL_MARGIN',
  'period':f'{START}/{END}','initial_capital_usd':CAPITAL,'final_equity_usd':round(final,6),'net_return_pct':round((final/CAPITAL-1)*100,6),'cagr_pct':round(cagr,6),
  'daily_mtm_max_drawdown_pct':round(maximum,6),'drawdown_peak_date':str(pair[0]),'drawdown_trough_date':str(pair[1]),'minimum_equity_usd':round(min(v for _,v in combined),6),
  'candidate':{'closed_trades':len(trades),'profit_factor':round(wins/loss,6) if loss else None,'net_closed_pnl_usd':round(sum(t['pnl_usd'] for t in trades),6),'extra_financing_usd':round(extra_financing,6),'skipped_margin':skipped_margin,'skipped_unaffordable':skipped_price,'open_positions_excluded':len(positions)},
  'base':{'cagr_pct':15.99959,'return_pct':56.041808,'drawdown_pct':15.915973},
  'policy':{'base_priority':True,'borrow_limit_usd':BORROW_LIMIT,'slots':3,'notional_cap_per_position_usd':SLOT},
  'limitations':['Candidate uses only residual margin after frozen base orders.','Adjusted candidate resources retain the previously audited family data conventions.','No paper or live trading is authorized.'],
  'paper_authorized':False,'live_authorized':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('sqx',type=Path);p.add_argument('--fx',type=Path,required=True)
 for k in ('cat','msft','jpm','sgln'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--strategy-spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=evaluate(a.sqx,a.fx,{k:getattr(a,k) for k in ('cat','msft','jpm','sgln')},a.strategy_spec);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
