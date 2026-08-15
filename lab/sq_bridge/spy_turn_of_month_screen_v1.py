#!/usr/bin/env python3
"""Single-rule, preregistered SPY turn-of-month falsification."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from datetime import date
from pathlib import Path

SPEC=Path(__file__).with_name('spy_turn_of_month_preregistration_v1.json')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path,allow_oos=False):
 rows=[]
 for raw in csv.reader(path.open(newline='',encoding='utf-8-sig')):
  if not raw or raw[0].lower()=='date': continue
  day=date.fromisoformat(raw[0].replace('.','-'))
  if not allow_oos and day>=date(2024,1,1): raise ValueError('OOS row leaked into development')
  offset=2 if len(raw)>1 and ':' in raw[1] else 1
  rows.append((day,float(raw[offset+3])))
 if not rows or any(a[0]>=b[0] for a,b in zip(rows,rows[1:])): raise ValueError('rows must be ordered and unique')
 return rows
def trades(rows):
 months={}
 for day,close in rows: months.setdefault((day.year,day.month),[]).append((day,close))
 keys=sorted(months);out=[]
 for left,right in zip(keys,keys[1:]):
  if (right[0]*12+right[1])-(left[0]*12+left[1])!=1 or len(months[left])<2 or len(months[right])<3: continue
  entry=months[left][-2];exit_=months[right][2]
  out.append({'entry':entry[0],'exit':exit_[0],'gross_return':exit_[1]/entry[1]-1})
 return out
def metrics(values,start,end,friction):
 returns=[x['gross_return'] for x in values if start<=x['entry']<=end and x['exit']<=end]
 net=[x-friction for x in returns];equity=peak=1.;dd=0.;wins=sum(max(x,0) for x in net);losses=sum(max(-x,0) for x in net)
 for value in net: equity*=1+value;peak=max(peak,equity);dd=max(dd,1-equity/peak)
 mean=sum(returns)/len(returns) if returns else 0.;variance=sum((x-mean)**2 for x in returns)/(len(returns)-1) if len(returns)>1 else 0.;t=mean/(math.sqrt(variance/len(returns))) if variance else None
 gross_wins=sum(max(x,0) for x in returns);gross_losses=sum(max(-x,0) for x in returns)
 return {'trades':len(returns),'gross_return_pct':(math.prod(1+x for x in returns)-1)*100,'gross_profit_factor':gross_wins/gross_losses if gross_losses else None,'net_return_pct':(equity-1)*100,'net_profit_factor':wins/losses if losses else None,'net_maximum_drawdown_pct':dd*100,'gross_mean_trade_pct':mean*100,'gross_t_stat':t,'positive_trades':sum(x>0 for x in returns)}
def develop(source):
 spec=json.loads(SPEC.read_text());rows=load(source);values=trades(rows);friction=spec['economics']['round_trip_friction_bps']/10000;periods={k:tuple(map(date.fromisoformat,v)) for k,v in spec['periods'].items() if k!='oos_2024'};m={k:metrics(values,*window,friction) for k,window in periods.items()};g=spec['gates'];combined=metrics(values,periods['train'][0],periods['validation'][1],friction)
 passed=m['train']['trades']>=g['train_minimum_trades'] and m['validation']['trades']>=g['validation_minimum_trades'] and all((x['gross_profit_factor'] or 0)>=g['minimum_gross_profit_factor_each_period'] and (x['net_profit_factor'] or 0)>=g['minimum_net_profit_factor_each_period'] and x['net_return_pct']>0 and x['net_maximum_drawdown_pct']<=g['maximum_net_drawdown_pct'] for x in m.values()) and (combined['gross_t_stat'] or 0)>=g['minimum_combined_one_sided_t_stat']
 return {'schema_version':1,'decision':'PASS_OPEN_SINGLE_OOS_2024' if passed else 'REJECT_DEVELOPMENT','preregistration_sha256':sha(SPEC),'source_sha256':sha(source),'rule_id':spec['rule']['id'],'metrics':m,'combined':combined,'oos_accessed':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False}
def evaluate_oos(source,development):
 spec=json.loads(SPEC.read_text());dev=json.loads(development.read_text())
 if dev['decision']!='PASS_OPEN_SINGLE_OOS_2024' or dev['preregistration_sha256']!=sha(SPEC): raise ValueError('development gate or frozen spec failed')
 rows=load(source,allow_oos=True);window=tuple(map(date.fromisoformat,spec['periods']['oos_2024']));result=dict(dev);result['oos_2024']=metrics(trades(rows),*window,spec['economics']['round_trip_friction_bps']/10000);result['oos_accessed']=True;result['oos_source_sha256']=sha(source);o=result['oos_2024'];result['decision']='PASS_STATISTICAL_EDGE' if o['trades']>=10 and (o['gross_profit_factor'] or 0)>=1.1 and (o['net_profit_factor'] or 0)>=1 and o['net_return_pct']>0 else 'REJECT_OOS_2024';return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--oos',action='store_true');p.add_argument('--development',type=Path);a=p.parse_args();x=evaluate_oos(a.source,a.development) if a.oos else develop(a.source);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'decision':x['decision'],'metrics':x.get('metrics'),'combined':x.get('combined'),'oos_2024':x.get('oos_2024')},indent=2))
if __name__=='__main__': main()
