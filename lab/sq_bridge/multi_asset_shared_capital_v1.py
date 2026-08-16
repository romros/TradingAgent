#!/usr/bin/env python3
"""Audit one frozen whole-share shared-capital policy for the new edge."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
from lab.sq_bridge.multi_asset_known_edge_funnel_v1 import ROOT,load,sma

def run(data,capital,start,end,cfg):
 max_positions=cfg['allocation']['maximum_concurrent_positions'];commission=cfg['costs']['commission_usd_per_order'];slip=cfg['costs']['slippage_bps_per_side']/10000
 indexed={asset:{row['date']:index for index,row in enumerate(rows)} for asset,rows in data.items()};dates=sorted({row['date'] for rows in data.values() for row in rows if start<=row['date']<=end});cash=capital;positions={};trades=[];peak=capital;dd=0;skipped=0
 for day in dates:
  # Exit first at today's open after ten complete asset-session advances.
  for asset,pos in list(positions.items()):
   index=indexed[asset].get(day)
   if index is not None and index-pos['entry_index']>=10:
    price=data[asset][index]['open']*(1-slip);proceeds=pos['shares']*price-commission;cash+=proceeds;pnl=proceeds-pos['cost'];trades.append({'asset':asset,'entry':pos['entry_date'],'exit':day,'pnl':pnl});del positions[asset]
  slots=max_positions-len(positions);signals=[]
  if slots:
   for asset,rows in data.items():
    if asset in positions:continue
    index=indexed[asset].get(day)
    if index is None or index<201:continue
    signal=index-1;average=sma(rows,signal,200)
    if average is not None and rows[signal]['close']>average and all(rows[j]['close']<rows[j-1]['close'] for j in range(signal-2,signal+1)):
     strength=rows[signal]['close']/rows[signal-3]['close']-1;signals.append((strength,asset,index))
   for _,asset,index in sorted(signals)[:slots]:
    equity=cash+sum(pos['shares']*data[name][indexed[name][day]]['open'] for name,pos in positions.items() if day in indexed[name]);budget=min(cash,equity/max_positions);price=data[asset][index]['open']*(1+slip);shares=math.floor((budget-commission)/price)
    if shares<1:skipped+=1;continue
    cost=shares*price+commission;cash-=cost;positions[asset]={'shares':shares,'cost':cost,'entry_date':day,'entry_index':index}
  equity=cash
  for asset,pos in positions.items():
   index=indexed[asset].get(day)
   equity+=pos['shares']*(data[asset][index]['close'] if index is not None else data[asset][pos['entry_index']]['open'])
  peak=max(peak,equity);dd=max(dd,(peak-equity)/peak*100)
 # Positions still open at the boundary are excluded and restored at entry cost.
 cash+=sum(pos['cost'] for pos in positions.values());wins=sum(max(t['pnl'],0) for t in trades);loss=sum(max(-t['pnl'],0) for t in trades)
 return {'trades':len(trades),'return_pct':(cash/capital-1)*100,'net_pnl_usd':cash-capital,'profit_factor':wins/loss if loss else None,'maximum_mark_to_market_drawdown_pct':dd,'skipped_unaffordable_signals':skipped,'open_positions_excluded':len(positions)}
def evaluate(strategy_spec:Path,capital_spec:Path):
 strategy=json.loads(strategy_spec.read_text());cfg=json.loads(capital_spec.read_text());data={asset:load(ROOT/path) for asset,path in strategy['assets'].items()};results={}
 for capital in cfg['capital_scenarios_usd']:
  results[str(capital)]={stage:run(data,capital,*bounds,cfg) for stage,bounds in cfg['periods'].items()}
 return {'schema_version':1,'decision':'PASS_SHARED_CAPITAL_DIAGNOSTIC','policy':cfg['allocation'],'results':results,'diagnostic_only':True,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--strategy-spec',type=Path,required=True);p.add_argument('--capital-spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=evaluate(a.strategy_spec,a.capital_spec);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
