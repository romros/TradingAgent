#!/usr/bin/env python3
"""Transfer-first screen of frozen, known daily strategy families."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(path):
 raw=list(csv.reader(path.open(newline='',encoding='utf-8-sig')));names=('date','time','open','high','low','close','volume');out=[]
 if raw and raw[0] and raw[0][0].lower()=='date': header=raw.pop(0)
 else: header=names
 for values in raw:
  row=dict(zip(header,values));row['date']=row['date'].replace('.','-')
  out.append({'date':row['date'],'open':float(row['open']),'high':float(row['high']),'low':float(row['low']),'close':float(row['close'])})
 return out
def sma(rows,i,n):return sum(x['close'] for x in rows[i-n+1:i+1])/n if i+1>=n else None
def variants(spec):
 yield from ({'family':'trend_filter','sma':n} for n in spec['families']['trend_filter']['sma'])
 yield from ({'family':'donchian','entry':a,'exit':b} for a,b in zip(spec['families']['donchian']['entry'],spec['families']['donchian']['exit']))
 for n in spec['families']['trend_pullback']['sma']:
  for down in spec['families']['trend_pullback']['down_days']:
   for hold in spec['families']['trend_pullback']['hold_days']:yield {'family':'trend_pullback','sma':n,'down_days':down,'hold_days':hold}
def simulate(rows,v,econ):
 cash=econ['capital_usd'];position=None;trades=[];slip=econ['slippage_bps_per_side']/10000;commission=econ['commission_usd_per_order']
 for i in range(1,len(rows)-1):
  exit_signal=False
  if position:
   if v['family']=='trend_filter': exit_signal=rows[i]['close']<sma(rows,i,v['sma'])
   elif v['family']=='donchian' and i>=v['exit']:exit_signal=rows[i]['close']<min(x['low'] for x in rows[i-v['exit']:i])
   else:exit_signal=i-position['signal_index']>=v['hold_days']
  if position and exit_signal:
   price=rows[i+1]['open']*(1-slip);pnl=position['shares']*(price-position['price'])-2*commission;cash+=pnl
   trades.append({'entry':position['date'],'exit':rows[i+1]['date'],'pnl':pnl});position=None
  if position:continue
  enter=False
  if v['family']=='trend_filter':
   avg=sma(rows,i,v['sma']);enter=avg is not None and rows[i]['close']>avg
  elif v['family']=='donchian' and i>=v['entry']:enter=rows[i]['close']>max(x['high'] for x in rows[i-v['entry']:i])
  elif v['family']=='trend_pullback' and i>=max(v['sma'],v['down_days']):
   avg=sma(rows,i,v['sma']);enter=rows[i]['close']>avg and all(rows[j]['close']<rows[j-1]['close'] for j in range(i-v['down_days']+1,i+1))
  if enter:
   price=rows[i+1]['open']*(1+slip);shares=math.floor((cash-commission)/price)
   if shares>=1:position={'price':price,'shares':shares,'date':rows[i+1]['date'],'signal_index':i}
 return trades
def in_period(trade,start,end):return start<=trade['entry'] and trade['exit']<=end
def metrics(trades,start,end,capital):
 chosen=[t for t in trades if in_period(t,start,end)];wins=sum(max(t['pnl'],0) for t in chosen);loss=sum(max(-t['pnl'],0) for t in chosen);eq=peak=capital;dd=0
 for t in chosen:eq+=t['pnl'];peak=max(peak,eq);dd=max(dd,(peak-eq)/peak*100)
 return {'trades':len(chosen),'net_pnl_usd':eq-capital,'return_pct':(eq/capital-1)*100,'profit_factor':wins/loss if loss else None,'maximum_drawdown_pct':dd}
def pool(rows,capital):
 trades=sum(x['metrics']['trades'] for x in rows);wins=sum(x['wins'] for x in rows);loss=sum(x['loss'] for x in rows);equity=peak=capital;dd=0
 # Equal-weight sleeves: each asset backtest used the same reference capital,
 # so divide every realized PnL by the frozen universe size.
 events=sorted((t['exit'],t['pnl']/len(rows)) for x in rows for t in x['selected'])
 for _,pnl in events:equity+=pnl;peak=max(peak,equity);dd=max(dd,(peak-equity)/peak*100)
 return {'trades':trades,'profit_factor':wins/loss if loss else None,'return_pct':sum(x['metrics']['return_pct'] for x in rows)/len(rows),'maximum_drawdown_pct':dd}
def evaluate(spec_path,oos=False,development=None):
 spec=json.loads(spec_path.read_text());data={a:load(ROOT/p) for a,p in spec['assets'].items()};periods=spec['periods'];econ=spec['economics'];results=[]
 allowed=None
 if oos:
  dev=json.loads(development.read_text())
  if dev['decision']!='PASS_FREEZE_ONE_BEFORE_OOS':raise ValueError('development did not open OOS')
  allowed=dev['selected_variant']
 for v in variants(spec):
  if allowed is not None and v!=allowed:continue
  assets={};summaries={'train':[],'validation':[],'oos':[]}
  for asset,bars in data.items():
   all_trades=simulate(bars,v,econ);assets[asset]={}
   for stage,(start,end) in periods.items():
    if stage=='oos' and not oos:continue
    selected=[t for t in all_trades if in_period(t,start,end)];m=metrics(all_trades,start,end,econ['capital_usd']);assets[asset][stage]=m;summaries[stage].append({'metrics':m,'selected':selected,'wins':sum(max(t['pnl'],0) for t in selected),'loss':sum(max(-t['pnl'],0) for t in selected)})
  pooled={stage:pool(values,econ['capital_usd']) for stage,values in summaries.items() if values};results.append({'variant':v,'assets':assets,'pooled':pooled})
 if oos:
  row=results[0];o=row['pooled']['oos'];names=list(data);loo={name:pool([value for index,value in enumerate(summaries['oos']) if names[index]!=name],econ['capital_usd']) for name in names}
  concentration_passed=all(value['return_pct']>0 and (value['profit_factor'] or 0)>=1.05 for value in loo.values())
  passed=o['trades']>=20 and (o['profit_factor'] or 0)>=1.10 and o['return_pct']>0 and o['maximum_drawdown_pct']<=25 and concentration_passed
  return {'schema_version':1,'decision':'PASS_RESEARCH_EDGE' if passed else 'REJECT_OOS_CONCENTRATION','selected_variant':allowed,'result':row,'leave_one_asset_out_oos':loo,'concentration_gate':'every leave-one-asset-out portfolio return>0 and PF>=1.05','concentration_passed':concentration_passed,'oos_accessed':True,'paper_authorized':False,'live_authorized':False}
 gate=spec['development_gate'];eligible=[]
 for row in results:
  train=row['pooled']['train'];val=row['pooled']['validation'];positive=sum(x['validation']['return_pct']>0 for x in row['assets'].values());strong=sum((x['validation']['profit_factor'] or 0)>=1.10 for x in row['assets'].values())
  checks={'train_pf':(train['profit_factor'] or 0)>=gate['minimum_pooled_train_pf'],'train_trades':train['trades']>=gate['minimum_pooled_train_trades'],'positive_assets':positive>=gate['minimum_assets_positive_validation'],'strong_assets':strong>=gate['minimum_assets_pf_1_10_validation'],'validation_pf':(val['profit_factor'] or 0)>=gate['minimum_pooled_validation_pf'],'validation_trades':val['trades']>=gate['minimum_pooled_validation_trades'],'validation_drawdown':val['maximum_drawdown_pct']<=gate['maximum_pooled_validation_drawdown_pct']};row['checks']=checks;row['positive_assets']=positive;row['strong_assets']=strong
  if all(checks.values()):eligible.append(row)
 eligible.sort(key=lambda r:(-r['strong_assets'],-(r['pooled']['validation']['profit_factor'] or 0),r['pooled']['validation']['maximum_drawdown_pct'],json.dumps(r['variant'],sort_keys=True)))
 selected=eligible[0]['variant'] if eligible else None
 return {'schema_version':1,'decision':'PASS_FREEZE_ONE_BEFORE_OOS' if selected else 'REJECT_DEVELOPMENT','spec_sha256':sha(spec_path),'evaluated_variants':len(results),'eligible_variants':len(eligible),'selected_variant':selected,'results':results,'oos_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--oos',action='store_true');p.add_argument('--development',type=Path);a=p.parse_args();r=evaluate(a.spec,a.oos,a.development);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r.get(k) for k in ('decision','evaluated_variants','eligible_variants','selected_variant')},indent=2))
if __name__=='__main__':main()
