#!/usr/bin/env python3
"""Frozen seven-equity monthly long/cash time-series momentum screen."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from lab.sq_bridge.equity_momentum_portfolio_v1 import load, metrics, rebalance_indices

HERE=Path(__file__).resolve().parent
SPEC=HERE/'equity_tsmom_preregistration_v1.json'; LOCK=HERE/'equity_tsmom_preregistration_v1.lock.json'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(frames, lookback, start, end, filter_on):
    days=sorted(set.intersection(*(set(v) for v in frames.values()))); points=rebalance_indices(days,'monthly_last_session'); out=[]; turns=0
    old={a:0 for a in frames}
    for si in points:
        ei=si+1; later=next((x for x in points if x>si),len(days)-1)+1; xi=min(later,len(days)-1)
        if si<lookback or ei>=len(days) or xi<=ei or not(start<=days[ei] and days[xi]<=end): continue
        wanted={a:int((frames[a][days[si]][1]/frames[a][days[si-lookback]][1]-1)>0) if filter_on else 1 for a in frames}
        turns+=sum(abs(wanted[a]-old[a]) for a in frames)/len(frames); old=wanted
        ret=sum(wanted[a]*(frames[a][days[xi]][0]/frames[a][days[ei]][0]-1) for a in frames)/len(frames)
        out.append((days[xi],ret))
    return {'metrics':metrics(out),'turnover_one_way':turns}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--asset',action='append',required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--spec',type=Path,default=SPEC); ap.add_argument('--lock',type=Path,default=LOCK); a=ap.parse_args()
    lock=json.loads(a.lock.read_text()); spec=json.loads(a.spec.read_text())
    if sha(a.spec)!=lock['preregistration_sha256']: raise ValueError('lock mismatch')
    src=dict(x.split('=',1) for x in a.asset)
    if set(src)!=set(spec['assets']): raise SystemExit('frozen universe required')
    frames={k:load(Path(v)) for k,v in src.items()}; report={'schema_version':1,'preregistration_sha256':sha(a.spec),'periods':{},'holdout_2025_accessed':False,'optimized':False}
    for name,bounds in spec['periods'].items():
        if name=='holdout_2025': continue
        report['periods'][name]={'benchmark':run(frames,63,*bounds,False),'variants':{str(lb):run(frames,lb,*bounds,True) for lb in (63,126,252)}}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps({p:{k:v['metrics'] for k,v in d['variants'].items()} for p,d in report['periods'].items()},indent=2))
if __name__=='__main__': main()
