#!/usr/bin/env python3
"""Falsify a frozen diversified futures TSMOM rule on continuous proxies."""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;SPEC=HERE/'diversified_futures_tsmom_preregistration_v1.json';LOCK=HERE/'diversified_futures_tsmom_preregistration_v1.lock.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):
 rows=[]
 with Path(path).open(newline='',encoding='utf-8-sig') as stream:
  for row in csv.DictReader(stream):rows.append((dt.date.fromisoformat(row['date']),float(row['open']),float(row['close'])))
 if any(open_<=0 or close<=0 for _,open_,close in rows):raise ValueError('non-positive continuous price')
 return rows
def monthly(rows):
 months={}
 for i,row in enumerate(rows):months.setdefault((row[0].year,row[0].month),[]).append(i)
 keys=sorted(months);out={};closes=[x[2] for x in rows]
 for k in range(1,len(keys)-1):
  prior,current,nxt=keys[k-1],keys[k],keys[k+1]
  if current[0]*12+current[1]!=prior[0]*12+prior[1]+1 or nxt[0]*12+nxt[1]!=current[0]*12+current[1]+1:continue
  signal_i=months[prior][-1];entry_i=months[current][0];exit_i=months[nxt][0]
  if signal_i<252 or signal_i<60:continue
  daily=[closes[i]/closes[i-1]-1 for i in range(signal_i-59,signal_i+1)];mean=sum(daily)/len(daily);vol=math.sqrt(sum((x-mean)**2 for x in daily)/(len(daily)-1))*math.sqrt(252)
  out[current]={'date':rows[entry_i][0],'return':rows[exit_i][1]/rows[entry_i][1]-1,'side':1 if closes[signal_i]/closes[signal_i-252]-1>0 else -1,'vol':vol}
 return out
def capped_inverse_vol(points,cap=.3):
 raw={k:1/v['vol'] for k,v in points.items()};weights={};remaining=1.;pool=set(raw)
 while pool:
  total=sum(raw[k] for k in pool);candidate={k:remaining*raw[k]/total for k in pool};capped={k for k,v in candidate.items() if v>cap}
  if not capped:weights.update(candidate);break
  for k in capped:weights[k]=cap;remaining-=cap;pool.remove(k)
 return weights
def portfolio(series,cost):
 common=sorted(set.intersection(*(set(x) for x in series.values())));old={k:0. for k in series};rows=[]
 for month in common:
  points={k:v[month] for k,v in series.items()};weights=capped_inverse_vol(points);target={k:weights[k]*points[k]['side'] for k in points};turnover=sum(abs(target[k]-old.get(k,0)) for k in target);legs={k:weights[k]*points[k]['side']*points[k]['return'] for k in points};rows.append({'date':points[next(iter(points))]['date'],'return':sum(legs.values())-turnover*cost,'gross_return':sum(legs.values()),'turnover':turnover,'legs':legs});old=target
 return rows
def select(rows,start,end):return [x for x in rows if start<=x['date']<=end]
def metrics(rows):
 returns=[x['return'] for x in rows];n=len(returns)
 if not n:return {'months':0}
 mean=sum(returns)/n;sd=math.sqrt(sum((x-mean)**2 for x in returns)/(n-1));equity=peak=1.;dd=0.
 for value in returns:equity*=1+value;peak=max(peak,equity);dd=max(dd,1-equity/peak)
 return {'months':n,'total_return':equity-1,'annualized_return':equity**(12/n)-1,'annualized_sharpe':mean/sd*math.sqrt(12),'maximum_drawdown':dd,'average_monthly_turnover':sum(x['turnover'] for x in rows)/n}
def run(paths):
 spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock['preregistration_sha256'] or lock['proxy_performance_accessed']:raise ValueError('proxy lock mismatch')
 valid={};quality={}
 for key,path in paths.items():
  try:valid[key]=monthly(load(path));quality[key]={'valid':True,'months':len(valid[key]),'sha256':sha(path)}
  except ValueError as error:quality[key]={'valid':False,'reason':str(error),'sha256':sha(path)}
 if len(valid)<spec['gates']['minimum_assets_with_80_percent_period_coverage']:return {'schema_version':1,'decision':'REJECT_PROXY_QUALITY','quality':quality,'proxy_performance_accessed':False}
 rows=portfolio(valid,spec['economics']['turnover_cost_bps']/10000);periods={k:select(rows,*map(dt.date.fromisoformat,v)) for k,v in spec['periods'].items()};report={k:metrics(v) for k,v in periods.items()};combined=metrics([x for k in ('validation','oos','recent_holdout') for x in periods[k]]);contribution={asset:sum(row['legs'].get(asset,0) for row in [x for k in ('validation','oos','recent_holdout') for x in periods[k]]) for asset in valid};positive_classes=len({spec['instruments'][asset]['class'] for asset,value in contribution.items() if value>0});g=spec['gates'];passed=report['validation']['total_return']>g['validation_return_gt'] and report['oos']['total_return']>g['oos_return_gt'] and report['recent_holdout']['total_return']>g['recent_holdout_return_gt'] and combined['annualized_sharpe']>=g['combined_validation_oos_recent_annualized_sharpe_gte'] and combined['maximum_drawdown']<=g['combined_maximum_drawdown_lte'] and positive_classes>=g['minimum_positive_asset_classes_combined']
 return {'schema_version':1,'decision':'PASS_PROXY_EDGE_REQUIRES_BROKER_ROLL_VALIDATION' if passed else 'REJECT_PROXY_EDGE','preregistration_sha256':sha(SPEC),'quality':quality,'periods':report,'combined_validation_oos_recent':combined,'gross_contribution_by_instrument':contribution,'positive_asset_classes':positive_classes,'proxy_performance_accessed':True,'optimized':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--asset',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();paths={k:Path(v) for k,v in (x.split('=',1) for x in a.asset)};expected=set(json.loads(SPEC.read_text())['instruments'])
 if set(paths)!=expected:raise ValueError('frozen universe required')
 result=run(paths);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
