#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,itertools,json
from datetime import date
from pathlib import Path
H=Path(__file__).resolve().parent; S=H/'ibkr_medium_term_momentum_preregistration_v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
 r=[]
 for x in csv.reader(p.open(newline='',encoding='utf-8-sig')):
  if not x or x[0].lower()=='date':continue
  d=date.fromisoformat(x[0].replace('.','-'))
  if d.year>=2025:raise ValueError('post-2024 sealed')
  off=2 if '.' in x[0] else 1;r.append((d,*map(float,x[off:off+4])))
 return r
def trades(r,look,hold,filt):
 c=[x[4] for x in r];out=[];last=-1
 for i in range(max(252,look),len(r)-hold-2):
  if r[i][0].month==r[i+1][0].month or i+1<=last:continue
  if c[i]/c[i-look]-1<=0 or (filt and c[i]<=sum(c[i-199:i+1])/200):continue
  en=i+1;ex=en+hold
  out.append({'entry':r[en][0],'return':r[ex][1]/r[en][1]-1-.003});last=ex
 return out
def met(t):
 eq=pk=1.;dd=gp=gl=0
 for x in t:
  q=x['return'];eq*=1+q;pk=max(pk,eq);dd=max(dd,1-eq/pk);gp+=max(q,0);gl+=max(-q,0)
 return {'trades':len(t),'return':eq-1,'profit_factor':gp/gl if gl else None,'max_drawdown':dd}
def main():
 a=argparse.ArgumentParser();a.add_argument('--asset',action='append',required=True);a.add_argument('--output',type=Path,required=True);z=a.parse_args();s=json.loads(S.read_text());ps=dict(x.split('=',1) for x in z.asset)
 if set(ps)!=set(s['assets']):raise ValueError('frozen universe required')
 fs={k:load(Path(v)) for k,v in ps.items()};results=[];start=date.fromisoformat(s['periods']['validation'][0]);end=date.fromisoformat(s['periods']['oos'][1])
 for p in itertools.product(s['grid']['lookback_sessions'],s['grid']['holding_sessions'],s['grid']['sma200_filter']):
  by={};pool=[]
  for k,r in fs.items():q=[x for x in trades(r,*p) if start<=x['entry']<=end];by[k]=met(q);pool+=q
  m=met(sorted(pool,key=lambda x:x['entry']));g=s['gates'];ok=m['trades']>=g['minimum_trades'] and (m['profit_factor'] or 0)>=g['minimum_profit_factor'] and m['return']>0 and m['max_drawdown']<=g['maximum_drawdown']
  results.append({'parameters':dict(zip(('lookback_sessions','holding_sessions','sma200_filter'),p)),'combined_validation_oos':m,'by_asset':by,'pass':ok})
 cen=next(x for x in results if x['parameters']==s['central_variant']);passing=sum(x['pass'] for x in results);positive=sum(x['return']>0 for x in cen['by_asset'].values());g=s['gates'];decision='PASS_FAMILY_TO_NATIVE_SQ' if passing>=g['minimum_passing_variants'] and positive>=g['minimum_positive_assets_central'] else 'REJECT_FAMILY'
 out={'schema_version':1,'decision':decision,'preregistration_sha256':sha(S),'passing_variants':passing,'central_positive_assets':positive,'central_variant':cen,'results':results,'optimized':False,'post_2024_accessed':False};z.output.parent.mkdir(parents=True,exist_ok=True);z.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ('decision','passing_variants','central_positive_assets')},indent=2))
if __name__=='__main__':main()
