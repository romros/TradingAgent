#!/usr/bin/env python3
"""Chronologically independent AAPL open-to-close confirmation."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;SPEC=HERE/'aapl_intraday_confirmation_preregistration_v1.json';LOCK=HERE/'aapl_intraday_confirmation_preregistration_v1.lock.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):
 out={}
 with Path(path).open(newline='',encoding='utf-8-sig') as stream:
  for row in csv.reader(stream):
   if not row or row[0].lower()=='date':continue
   day=row[0].replace('.','-');offset=2 if len(row)>1 and ':' in row[1] else 1
   if '2025-01-02'<=day<='2026-07-31':out[day]=(float(row[offset]),float(row[offset+3]))
 return out
def metrics(prices,capital,commission,slippage):
 equity=float(capital);peak=equity;dd=0.;returns=[];gross=[];skipped=0
 for day,(open_,close) in sorted(prices.items()):
  gross.append(close/open_-1);entry=open_*(1+slippage/2);exit_=close*(1-slippage/2);shares=math.floor(equity/entry)
  if shares<1:skipped+=1;continue
  before=equity;pnl=shares*(exit_-entry)-2*commission;equity+=pnl;returns.append(pnl/before);peak=max(peak,equity);dd=max(dd,1-equity/peak)
 mean=sum(returns)/len(returns);sd=math.sqrt(sum((x-mean)**2 for x in returns)/(len(returns)-1));wins=sum(max(x,0) for x in returns);losses=sum(max(-x,0) for x in returns)
 return {'sessions':len(returns),'skipped':skipped,'net_return':equity/capital-1,'net_mean_daily_return':mean,'net_one_sided_t_stat':mean/(sd/math.sqrt(len(returns))),'net_profit_factor':wins/losses if losses else None,'net_maximum_drawdown':dd,'gross_mean_bps':sum(gross)/len(gross)*10000,'positive_net_sessions':sum(x>0 for x in returns)}
def parity(primary,secondary):
 common=sorted(set(primary)&set(secondary));left=[primary[d][1]/primary[d][0]-1 for d in common];right=[secondary[d][1]/secondary[d][0]-1 for d in common];lm=sum(left)/len(left);rm=sum(right)/len(right);cov=sum((a-lm)*(b-rm) for a,b in zip(left,right));den=math.sqrt(sum((a-lm)**2 for a in left)*sum((b-rm)**2 for b in right));return {'common_sessions':len(common),'return_correlation':cov/den,'direction_agreement':sum((a>=0)==(b>=0) for a,b in zip(left,right))/len(common),'mean_difference_bps':sum(a-b for a,b in zip(left,right))/len(common)*10000}
def run(primary_path,parity_path):
 spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock['preregistration_sha256'] or lock['confirmation_performance_accessed']:raise ValueError('confirmation lock mismatch')
 primary=load(primary_path);secondary=load(parity_path);economics=spec['economics'];results={str(cap):metrics(primary,cap,economics['commission_per_order_usd'],economics['round_trip_slippage_bps']/10000) for cap in economics['capital_usd']};cross=parity(primary,secondary);g=spec['gates'];m=results[str(g['must_pass_at_capital_usd'])];passed=m['sessions']>=g['minimum_confirmation_sessions'] and m['net_one_sided_t_stat']>=g['primary_net_one_sided_t_stat_gte'] and m['net_profit_factor']>=g['primary_net_profit_factor_gte'] and m['net_return']>g['primary_net_return_gt'] and m['net_maximum_drawdown']<=g['primary_net_maximum_drawdown_lte'] and cross['return_correlation']>=g['daily_return_parity_correlation_gte'] and cross['direction_agreement']>=g['daily_return_direction_agreement_gte']
 return {'schema_version':1,'decision':'PASS_STATISTICAL_EDGE' if passed else 'REJECT_CONFIRMATION','preregistration_sha256':sha(SPEC),'primary_source_sha256':sha(primary_path),'parity_source_sha256':sha(parity_path),'economics_by_capital':results,'source_parity':cross,'optimized':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--primary',type=Path,required=True);p.add_argument('--parity',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();x=run(a.primary,a.parity);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x,indent=2))
if __name__=='__main__':main()
