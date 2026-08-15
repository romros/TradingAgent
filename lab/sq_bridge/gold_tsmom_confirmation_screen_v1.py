#!/usr/bin/env python3
"""Independent recent confirmation of the discovered SGLN 12-month TSMOM rule."""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;SPEC=HERE/'gold_tsmom_confirmation_preregistration_v1.json';LOCK=HERE/'gold_tsmom_confirmation_preregistration_v1.lock.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):
 out={}
 with Path(path).open(newline='',encoding='utf-8-sig') as stream:
  for row in csv.reader(stream):
   if not row or row[0].lower()=='date':continue
   day=dt.date.fromisoformat(row[0].replace('.','-'));offset=2 if len(row)>1 and ':' in row[1] else 1;out[day]=(float(row[offset]),float(row[offset+3]))
 return out
def monthly(prices,cost):
 months={}
 for day in sorted(prices):months.setdefault((day.year,day.month),[]).append(day)
 keys=sorted(months);rows=[];old=0
 for i in range(12,len(keys)-1):
  next_key=keys[i+1]
  if next_key[0]*12+next_key[1]!=keys[i][0]*12+keys[i][1]+1:continue
  after=keys[i+2] if i+2<len(keys) else None
  if not after or after[0]*12+after[1]!=next_key[0]*12+next_key[1]+1:continue
  signal=months[keys[i]][-1];entry=months[next_key][0];exit_=months[after][0];position=int(prices[signal][1]>prices[months[keys[i-12]][-1]][1]);turn=abs(position-old);ret=position*(prices[exit_][0]/prices[entry][0]-1)-turn*cost;rows.append((entry,ret,position,turn));old=position
 return rows
def select(rows,start,end):return [row for row in rows if start<=row[0]<=end]
def metrics(rows):
 returns=[x[1] for x in rows];n=len(returns);mean=sum(returns)/n;sd=math.sqrt(sum((x-mean)**2 for x in returns)/(n-1));equity=peak=1.;dd=0.
 for value in returns:equity*=1+value;peak=max(peak,equity);dd=max(dd,1-equity/peak)
 return {'months':n,'invested_months':sum(x[2] for x in rows),'position_changes':sum(x[3] for x in rows),'total_return':equity-1,'annualized_return':equity**(12/n)-1,'annualized_sharpe':mean/sd*math.sqrt(12),'maximum_drawdown':dd}
def correlation(left,right):
 a={x[0]:x[1] for x in left};b={x[0]:x[1] for x in right};keys=sorted(set(a)&set(b));am=sum(a[k] for k in keys)/len(keys);bm=sum(b[k] for k in keys)/len(keys);den=math.sqrt(sum((a[k]-am)**2 for k in keys)*sum((b[k]-bm)**2 for k in keys));return {'months':len(keys),'correlation':sum((a[k]-am)*(b[k]-bm) for k in keys)/den if den else None}
def run(sgln_path,phau_path):
 spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock['preregistration_sha256'] or lock['confirmation_performance_accessed']:raise ValueError('confirmation lock mismatch')
 economics=spec['economics'];cost=economics['commission_each_position_change_eur']/economics['capital_eur_equivalent']+economics['slippage_each_position_change_bps']/10000;all_rows={'SGLN_L':monthly(load(sgln_path),cost),'PHAU_L':monthly(load(phau_path),cost)};start,end=map(dt.date.fromisoformat,spec['confirmation_period']);recent={k:select(v,start,end) for k,v in all_rows.items()};m={k:metrics(v) for k,v in recent.items()};combined=metrics(select(all_rows['SGLN_L'],dt.date(2019,1,1),end));cross=correlation(*recent.values());g=spec['gates'];candidate=m['SGLN_L'];control=m['PHAU_L'];passed=candidate['months']>=g['minimum_completed_candidate_months'] and candidate['total_return']>g['candidate_total_return_gt'] and candidate['annualized_sharpe']>=g['candidate_annualized_sharpe_gte'] and candidate['maximum_drawdown']<=g['candidate_maximum_drawdown_lte'] and control['total_return']>g['control_total_return_gt'] and (cross['correlation'] or -1)>=g['candidate_control_monthly_return_correlation_gte'] and combined['annualized_sharpe']>=g['combined_2019_2026_candidate_annualized_sharpe_gte'] and combined['maximum_drawdown']<=g['combined_2019_2026_candidate_maximum_drawdown_lte']
 return {'schema_version':1,'decision':'PASS_STATISTICAL_EDGE' if passed else 'REJECT_CONFIRMATION','preregistration_sha256':sha(SPEC),'sources':{'SGLN_L':sha(sgln_path),'PHAU_L':sha(phau_path)},'confirmation':m,'confirmation_transfer':cross,'candidate_combined_2019_2026':combined,'optimized':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--sgln',type=Path,required=True);p.add_argument('--phau',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();x=run(a.sgln,a.phau);a.output.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x,indent=2))
if __name__=='__main__':main()
