#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;SPEC=HERE/'connors_rsi2_preregistration_v1.json';LOCK=HERE/'connors_rsi2_preregistration_v1.lock.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
 if '2025' in p.name:raise ValueError('2025 sealed')
 out=[]
 for line in p.read_text().splitlines():
  if not line.strip():continue
  x=line.split(',');d=dt.datetime.strptime(x[0],'%Y.%m.%d').date()
  if d.year>=2025:raise ValueError('sealed row')
  out.append((d,float(x[2]),float(x[5])))
 return out
def rsi_wilder(closes,n=2):
 out=[None]*len(closes)
 if len(closes)<=n:return out
 gains=[max(closes[i]-closes[i-1],0) for i in range(1,len(closes))];losses=[max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
 ag=sum(gains[:n])/n;al=sum(losses[:n])/n
 out[n]=100 if al==0 else 100-100/(1+ag/al)
 for i in range(n+1,len(closes)):
  ag=(ag*(n-1)+gains[i-1])/n;al=(al*(n-1)+losses[i-1])/n;out[i]=100 if al==0 else 100-100/(1+ag/al)
 return out
def trades(rows):
 cs=[x[2] for x in rows];rsi=rsi_wilder(cs);out=[];entry=None
 for i in range(199,len(rows)-1):
  sma200=sum(cs[i-199:i+1])/200;sma5=sum(cs[i-4:i+1])/5
  if entry is None:
   if cs[i]>sma200 and rsi[i] is not None and rsi[i]<5:entry=(i+1,rows[i+1][1])
  elif i>=entry[0] and cs[i]>sma5:
   out.append({'entry':rows[entry[0]][0],'exit':rows[i+1][0],'return':rows[i+1][1]/entry[1]-1});entry=None
 return out
def in_period(ts,s,e):return [x for x in ts if s<=x['entry'] and x['exit']<=e]
def metrics(ts):
 rs=[x['return'] for x in ts];n=len(rs)
 if not n:return {'trades':0}
 mean=sum(rs)/n;sd=math.sqrt(sum((r-mean)**2 for r in rs)/(n-1)) if n>1 else 0;gp=sum(r for r in rs if r>0);gl=-sum(r for r in rs if r<0);eq=peak=1.;dd=0.
 for r in rs:eq*=1+r;peak=max(peak,eq);dd=max(dd,1-eq/peak)
 return {'trades':n,'wins':sum(r>0 for r in rs),'mean_return':mean,'total_return':eq-1,'profit_factor':gp/gl if gl else None,'t_stat':mean/(sd/math.sqrt(n)) if sd else None,'max_drawdown':dd}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock['preregistration_sha256']:raise ValueError('lock mismatch')
 paths=dict(x.split('=',1) for x in a.asset)
 if set(paths)!=set(spec['assets']):raise ValueError('frozen universe required')
 alltr={k:trades(load(Path(v))) for k,v in paths.items()};period_tr={};report={'schema_version':1,'preregistration_sha256':sha(SPEC),'optimized':False,'holdout_2025_accessed':False,'periods':{}}
 for p,b in spec['periods'].items():
  if p=='holdout_2025':continue
  s,e=map(dt.date.fromisoformat,b);by={k:in_period(v,s,e) for k,v in alltr.items()};pool=sorted((x for v in by.values() for x in v),key=lambda x:x['exit']);period_tr[p]=pool;report['periods'][p]={'pooled':metrics(pool),'by_asset':{k:metrics(v) for k,v in by.items()}}
 g=spec['gates'];v=metrics(period_tr['validation']);o=metrics(period_tr['oos_2024']);c=metrics(sorted(period_tr['validation']+period_tr['oos_2024'],key=lambda x:x['exit']));positive=sum((report['periods']['validation']['by_asset'][a].get('mean_return',0)*report['periods']['validation']['by_asset'][a].get('trades',0)+report['periods']['oos_2024']['by_asset'][a].get('mean_return',0)*report['periods']['oos_2024']['by_asset'][a].get('trades',0))>0 for a in paths)
 passed=(v['trades']>=g['validation_min_trades'] and o['trades']>=g['oos_min_trades'] and v['mean_return']>0 and o['mean_return']>0 and (v['profit_factor'] or 0)>=g['validation_and_oos_profit_factor_gte'] and (o['profit_factor'] or 0)>=g['validation_and_oos_profit_factor_gte'] and (c['t_stat'] or -999)>=g['combined_one_sided_t_stat_gte'] and c['max_drawdown']<=g['combined_max_drawdown_lte'] and positive>=g['minimum_assets_positive_combined'])
 report['decision']={'pass':passed,'combined_validation_oos':c,'positive_assets':positive};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
