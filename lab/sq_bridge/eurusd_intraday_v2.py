#!/usr/bin/env python3
from __future__ import annotations
import argparse, itertools, json, math
from pathlib import Path
import numpy as np, pandas as pd

ROOT=Path(__file__).resolve().parents[2]
SPLITS={"train":("2004-01-01","2013-12-31"),"validation":("2014-01-01","2018-12-31"),"oos":("2019-01-01","2023-12-31")}

def load_m15(root):
 import duckdb
 pattern=str(root/'EURUSD'/'tf=1m'/'year=*'/'month=*'/'data.parquet')
 q=f"""SELECT time_bucket(INTERVAL '15 minutes',to_timestamp(ts)) t,arg_min(open,ts) o,max(high) h,min(low) l,arg_max(close,ts) c,count(*) n FROM read_parquet('{pattern}') GROUP BY t ORDER BY t"""
 d=duckdb.sql(q).df(); d.index=pd.to_datetime(d.pop('t'),utc=True); return d[(d.n>=10)&(d.c>0)&(d.h>d.l)].loc['2004-01-01':]

def features(d):
 x=d.copy(); x['atr']=pd.concat([x.h-x.l,(x.h-x.c.shift()).abs(),(x.l-x.c.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
 x['body']=(x.c-x.o).abs(); x['ldn']=x.index.tz_convert('Europe/London'); x['ny']=x.index.tz_convert('America/New_York'); return x

def candidates():
 out=[]
 for fam in ('vol_expansion_continuation','vol_expansion_reversal'):
  for session,side in itertools.product(('london','overlap'),(-1,1)): out.append((fam,(session,1.5,1.25,1.5,4,side)))
 for side in (-1,1): out.append(('asian_range_breakout',(.1,1.0,1.5,side)))
 return out

_SESSION_CACHE={}

def session_days(d):
 key=id(d)
 if key not in _SESSION_CACHE:
  ldn=d.ldn; dates=pd.Series(ldn.dt.date,index=d.index); result=[]
  for _,idx in dates.groupby(dates).groups.items():
   pos=d.index.get_indexer(idx); result.append(([i for i in pos if 0<=ldn.iloc[i].hour<7],[i for i in pos if 8<=ldn.iloc[i].hour<12]))
  _SESSION_CACHE[key]=result
 return _SESSION_CACHE[key]

def trades(d,fam,p):
 rows=[]; last=-1
 if fam.startswith('vol_'):
  session,mult,smult,rr,hold,side=p; local=d.ldn if session=='london' else d.ny
  allowed=((local.dt.hour>=8)&(local.dt.hour<12)) if session=='london' else ((local.dt.hour>=8)&(local.dt.hour<11))
  impulse=np.sign(d.c-d.o); sig=allowed&(d.body>mult*d.atr)&(impulse==side)
  if fam.endswith('reversal'): side=-side
  for i in np.flatnonzero(sig):
   e=i+1
   if e<=last or e>=len(d): continue
   ep=float(d.o.iloc[e]); dist=float(d.atr.iloc[i]*smult)
   if not dist>0: continue
   end=min(e+hold-1,len(d)-1); window=d.iloc[e:end+1]; stop=ep-side*dist; target=ep+side*dist*rr; xp=float(window.c.iloc[-1])
   for bar in window.itertuples():
    hit_s=bar.l<=stop if side==1 else bar.h>=stop; hit_t=bar.h>=target if side==1 else bar.l<=target
    if hit_s or hit_t: xp=stop if hit_s else target; break
   rows.append((d.index[e],side*(xp-ep)/ep,dist/ep)); last=end
 else:
  buffer,smult,rr,side=p
  for asia,active in session_days(d):
   if not asia or not active: continue
   hi=float(d.h.iloc[asia].max()); lo=float(d.l.iloc[asia].min()); width=hi-lo; level=hi+buffer*width if side==1 else lo-buffer*width
   hit=next((i for i in active if (d.c.iloc[i]>level if side==1 else d.c.iloc[i]<level)),None)
   if hit is None or hit+1<=last or hit+1>=len(d): continue
   e=hit+1; ep=float(d.o.iloc[e]); dist=width*smult; stop=ep-side*dist; target=ep+side*dist*rr; xp=float(d.c.iloc[active[-1]])
   for bar in d.iloc[e:active[-1]+1].itertuples():
    hs=bar.l<=stop if side==1 else bar.h>=stop; ht=bar.h>=target if side==1 else bar.l<=target
    if hs or ht: xp=stop if hs else target; break
   rows.append((d.index[e],side*(xp-ep)/ep,dist/ep)); last=active[-1]
 return pd.DataFrame(rows,columns=['date','gross','stop'])

def metrics(t,bps):
 if t.empty:return {'n':0,'pf':0,'ev_usdc':-99,'dd':100,'positive_years':0}
 net=t.gross-bps/10000; pnl=net*(2/t.stop.clip(lower=.0005)); w=pnl[pnl>0].sum(); l=-pnl[pnl<0].sum(); eq=200+pnl.cumsum(); dd=(1-eq/eq.cummax()).max(); yr=pd.Series(pnl.values,index=pd.DatetimeIndex(t.date)).groupby(pd.DatetimeIndex(t.date).year).sum()
 return {'n':len(t),'pf':float(w/l) if l else 99,'ev_usdc':float(pnl.mean()),'dd':float(dd*100),'positive_years':float((yr>0).mean())}

def segment(t,name):
 a,b=SPLITS[name]; return t[(t.date>=a)&(t.date<=b)]

def run(root):
 d=features(load_m15(root)); rows=[]
 for fam in ('asian_range_breakout','vol_expansion_continuation','vol_expansion_reversal'):
  variants=[]
  for f,p in candidates():
   if f!=fam:continue
   t=trades(d,f,p); m=metrics(segment(t,'train'),15); score=m['pf']*math.sqrt(m['n']) if m['n']>=100 and m['ev_usdc']>0 else -1
   variants.append((score,p,t,m))
  score,p,t,tr=max(variants,key=lambda x:x[0]); periods={s:{c:metrics(segment(t,s),bps) for c,bps in [('base',8),('conservative',15),('stress',30)]} for s in SPLITS}
  v,o=periods['validation'],periods['oos']; gate=v['base']['n']>=100 and o['base']['n']>=100 and v['base']['pf']>=1.2 and o['base']['pf']>=1.2 and v['stress']['pf']>=1.05 and o['stress']['pf']>=1.05 and v['stress']['ev_usdc']>=.1 and o['stress']['ev_usdc']>=.1 and v['base']['positive_years']>=.6 and o['base']['positive_years']>=.6
  rows.append({'family':fam,'params':p,'train':tr,'periods':periods,'passes_pre_holdout':gate})
 return {'methodology':'methodology_eurusd_intraday_v2.json','coverage':{'first':str(d.index.min()),'last':str(d.index.max()),'bars':len(d)},'holdout_evaluated':False,'families':rows,'eligible':[x['family'] for x in rows if x['passes_pre_holdout']],'decision':'PASS_TO_SQCLI' if any(x['passes_pre_holdout'] for x in rows) else 'REJECT_NO_SQCLI'}

def main():
 p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); x=run(a.root); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(x,indent=2,default=str)+'\n'); print(json.dumps(x,indent=2,default=str))
if __name__=='__main__':main()
