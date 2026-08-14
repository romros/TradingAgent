#!/usr/bin/env python3
"""Frozen staged Connors-style RSI(2) index screen."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from datetime import date
from pathlib import Path
HERE=Path(__file__).resolve().parent; PREREG=HERE/'index_rsi2_preregistration_v1.json'; FROZEN='0513f3c38c3306de4c8e18af755ad72320e02f68719bb75f98928ae23ebdc833'

def load(path,ceiling):
    path=Path(path)
    if '2025' in path.name: raise ValueError('2025 sealed')
    out=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        first=f.readline(); f.seek(0)
        if first.lower().startswith('date,'):
            for r in csv.DictReader(f):
                d=date.fromisoformat(r['date']); o=float(r['open']); c=float(r['close'])
                if d>=date(2025,1,1): raise ValueError('2025 sealed row')
                if d<=ceiling: out.append((d,o,c))
        else:
            for r in csv.reader(f):
                d=date.fromisoformat(r[0].replace('.','-'))
                if d>=date(2025,1,1): raise ValueError('2025 sealed row')
                if d<=ceiling: out.append((d,float(r[2]),float(r[5])))
    return out

def indicators(rows):
    gains=[];losses=[];avg_g=avg_l=None;cl=[];out=[]
    for i,(d,o,c) in enumerate(rows):
        if cl:
            change=c-cl[-1];g=max(change,0);l=max(-change,0)
            gains.append(g);losses.append(l)
            if len(gains)==2: avg_g=sum(gains)/2;avg_l=sum(losses)/2
            elif len(gains)>2: avg_g=(avg_g+g)/2;avg_l=(avg_l+l)/2
        rsi=None if avg_g is None else (100 if avg_l==0 else 100-100/(1+avg_g/avg_l))
        out.append((d,o,c,rsi,sum(cl[-199:]+[c])/200 if len(cl)>=199 else None,sum(cl[-4:]+[c])/5 if len(cl)>=4 else None));cl.append(c)
    return out

def sim(rows,start,end):
    eq=peak=1000.;dd=0.;pos=None;entry=False;exit_=None;held=0;tr=[];last=None
    for d,o,c,rsi,s200,s5 in indicators(rows):
        if not start<=d<=end: continue
        last=(d,o,c)
        if pos and exit_:
            gross=pos[1]*(o-pos[0]);cost=pos[2]+1+.001*pos[1]*o;net=gross-cost;eq+=net;tr.append({'entry':pos[3].isoformat(),'exit':d.isoformat(),'net':net});pos=None;exit_=None
        if not pos and entry:
            q=math.floor(eq/o);entry=False
            if q: pos=(o,q,1+.001*q*o,d);held=0
        if pos:
            held+=1
            if s5 is not None and c>s5: exit_='sma5'
            elif held>=10: exit_='time'
            mark=eq+pos[1]*(c-pos[0])-pos[2]-1-.001*pos[1]*c
        else:
            if rsi is not None and s200 is not None and rsi<5 and c>s200: entry=True
            mark=eq
        peak=max(peak,mark);dd=max(dd,(peak-mark)/peak*100)
    if pos:
        d,o,c=last;gross=pos[1]*(c-pos[0]);cost=pos[2]+1+.001*pos[1]*c;net=gross-cost;eq+=net;tr.append({'entry':pos[3].isoformat(),'exit':d.isoformat(),'net':net})
    w=sum(x['net'] for x in tr if x['net']>0);l=-sum(x['net'] for x in tr if x['net']<0)
    return {'trades':len(tr),'return_pct':(eq/1000-1)*100,'pf':w/l if l else (1e9 if w else 0),'dd_pct':dd,'details':tr}

def agg(rs):
    ts=[t for r in rs.values() for t in r['details']];w=sum(t['net'] for t in ts if t['net']>0);l=-sum(t['net'] for t in ts if t['net']<0)
    return {'trades':len(ts),'pf':w/l if l else (1e9 if w else 0),'mean_return_pct':sum(r['return_pct'] for r in rs.values())/len(rs),'positive_assets':sum(r['return_pct']>0 for r in rs.values()),'max_dd_pct':max(r['dd_pct'] for r in rs.values())}
def gate(a): return a['trades']>=30 and a['pf']>=1.15 and a['mean_return_pct']>0 and a['positive_assets']>=2 and a['max_dd_pct']<=20
def main():
    p=argparse.ArgumentParser();p.add_argument('--asset',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if hashlib.sha256(PREREG.read_bytes()).hexdigest()!=FROZEN: raise ValueError('freeze mismatch')
    paths=dict(x.split('=',1) for x in a.asset)
    if sorted(paths)!=['CSPX','SPY','SXR8']: raise ValueError('exact assets required')
    pre={k:load(v,date(2023,12,31)) for k,v in paths.items()};train={k:sim(v,date(2017,1,1),date(2021,12,31)) for k,v in pre.items()};val={k:sim(v,date(2022,1,1),date(2023,12,31)) for k,v in pre.items()};ag=agg(val);ok=gate(ag)
    oos={'status':'SEALED'} if not ok else {k:sim(load(v,date(2024,12,31)),date(2024,1,1),date(2024,12,31)) for k,v in paths.items()}
    result={'train':train,'validation':val,'validation_aggregate':ag,'decision':'PASS_OPEN_OOS' if ok else 'REJECT_KEEP_OOS_SEALED','oos':oos};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'decision':result['decision'],'aggregate':ag,'returns':{k:v['return_pct'] for k,v in val.items()},'oos':oos},indent=2))
if __name__=='__main__':main()
