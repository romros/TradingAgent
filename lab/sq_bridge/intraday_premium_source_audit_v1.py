#!/usr/bin/env python3
"""Cross-provider falsification of the surprising Dukascopy stock intraday premium."""
from __future__ import annotations
import argparse,csv,datetime as dt,json,math
from pathlib import Path

def load_duka(path):
 out={}
 with path.open(newline='') as f:
  for raw in csv.reader(f):
   if not raw or raw[0].lower()=='date':continue
   d=dt.date.fromisoformat(raw[0].replace('.','-'))
   if d.year>=2025:raise ValueError('2025 sealed')
   # Canonical header CSV is date,OHLC; SQ generic is date,time,OHLC.
   offset=2 if len(raw)>1 and ':' in raw[1] else 1
   out[d]=(float(raw[offset]),float(raw[offset+3]))
 return out
def stats(x):
 n=len(x);m=sum(x)/n;sd=(sum((v-m)**2 for v in x)/(n-1))**.5
 return {'observations':n,'mean_bps':m*10000,'t_stat':m/(sd/n**.5),'positive_pct':100*sum(v>0 for v in x)/n}
def corr(a,b):
 ma,mb=sum(a)/len(a),sum(b)/len(b);den=(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))**.5
 return sum((x-ma)*(y-mb) for x,y in zip(a,b))/den
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True,help='TICKER=canonical.csv');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 import yfinance as yf
 report={'schema_version':1,'classification':'EXPLORATORY_SOURCE_AUDIT_NOT_CANDIDATE','period':'2022-01-01/2024-12-31','holdout_2025_accessed':False,'assets':{}}
 for item in a.asset:
  ticker,path=item.split('=',1);duka=load_duka(Path(path));frame=yf.download(ticker,start='2022-01-01',end='2025-01-01',auto_adjust=True,actions=False,progress=False)
  yahoo={stamp.date():(float(row[('Open',ticker)]),float(row[('Close',ticker)])) for stamp,row in frame.iterrows()}
  days=sorted(set(duka)&set(yahoo));dr=[duka[d][1]/duka[d][0]-1 for d in days];yr=[yahoo[d][1]/yahoo[d][0]-1 for d in days]
  diff=[(dr[i]-yr[i])*10000 for i in range(len(days))];report['assets'][ticker]={'dukas':stats(dr),'yahoo_adjusted':stats(yr),'daily_return_correlation':corr(dr,yr),'difference_bps':{'median':sorted(diff)[len(diff)//2],'mean':sum(diff)/len(diff),'max_abs':max(map(abs,diff))}}
 report['conclusion']='PASS_SOURCE_PARITY' if all(x['daily_return_correlation']>.99 and abs(x['difference_bps']['median'])<2 for x in report['assets'].values()) else 'REJECT_DUKASCOPY_INTRADAY_PREMIUM_AS_SOURCE_ARTIFACT'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
