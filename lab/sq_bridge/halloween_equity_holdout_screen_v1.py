#!/usr/bin/env python3
"""Evaluate the sealed 2024-2026 SPY Halloween holdout without tuning."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=HERE/'halloween_equity_holdout_preregistration_v1.json'
LOCK=HERE/'halloween_equity_holdout_preregistration_v1.lock.json'
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_open_by_month(path):
 result={}
 with Path(path).open(newline='',encoding='utf-8-sig') as stream:
  for row in csv.reader(stream):
   if not row or row[0].lower()=='date': continue
   day=row[0].replace('.','-');offset=2 if len(row)>1 and ':' in row[1] else 1
   result.setdefault(day[:7],(day,float(row[offset])))
 return result
def recent_trades(path,cost):
 opens=load_open_by_month(path);out=[]
 for year in (2024,2025):
  entry=opens.get(f'{year}-11');exit_=opens.get(f'{year+1}-05')
  if entry and exit_: out.append({'entry':entry[0],'exit':exit_[0],'return':exit_[1]/entry[1]-1-cost})
 return out
def metrics(returns):
 mean=sum(returns)/len(returns);variance=sum((x-mean)**2 for x in returns)/(len(returns)-1) if len(returns)>1 else 0.;t=mean/math.sqrt(variance/len(returns)) if variance else None
 equity=peak=1.;dd=0.;wins=sum(max(x,0) for x in returns);losses=sum(max(-x,0) for x in returns)
 for value in returns: equity*=1+value;peak=max(peak,equity);dd=max(dd,1-equity/peak)
 return {'trades':len(returns),'compounded_net_return':equity-1,'arithmetic_mean_trade':mean,'one_sided_t_stat':t,'net_profit_factor':wins/losses if losses else None,'maximum_drawdown':dd,'positive_trades':sum(x>0 for x in returns)}
def run(source,parent):
 spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock['preregistration_sha256'] or lock['performance_accessed']: raise ValueError('holdout lock mismatch')
 if sha(parent)!=spec['parent_result_sha256']: raise ValueError('parent result hash mismatch')
 old=json.loads(parent.read_text());historical=[x['return'] for stage in ('train','validation','oos') for x in old[stage]['SPY']['trades_detail']]
 recent=recent_trades(source,30/10000);combined=metrics(historical+[x['return'] for x in recent]);holdout=metrics([x['return'] for x in recent]) if recent else None;g=spec['gates']
 passed=len(recent)==2 and holdout['compounded_net_return']>g['holdout_compounded_net_return_gt'] and (combined['one_sided_t_stat'] or 0)>=g['all_nine_seasons_combined_one_sided_t_stat_gte'] and (combined['net_profit_factor'] or float('inf'))>=g['all_nine_seasons_net_profit_factor_gte'] and combined['maximum_drawdown']<=g['all_nine_seasons_maximum_drawdown_lte']
 return {'schema_version':1,'decision':'PASS_STATISTICAL_EDGE' if passed else 'REJECT_RECENT_HOLDOUT','preregistration_sha256':sha(SPEC),'parent_result_sha256':sha(parent),'holdout_source_sha256':sha(source),'historical_independent_seasons':len(historical),'holdout':holdout,'holdout_trades':recent,'combined_nine_seasons':combined,'performance_accessed':True,'optimized':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=run(a.source,a.parent);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
