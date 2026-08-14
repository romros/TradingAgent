#!/usr/bin/env python3
"""Single-variant, preregistered IBS daily reversal screen."""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, math
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=HERE/'ibs_reversion_preregistration_v1.json'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(path):
    if '2025' in path.name: raise ValueError('2025 filename sealed')
    out=[]
    for r in csv.reader(path.open()):
        day=dt.datetime.strptime(r[0],'%Y.%m.%d').date()
        if day.year>=2025: raise ValueError('2025 row sealed')
        # Supported adjusted Yahoo layout: date,time,open,high,low,close,...
        out.append({'date':day,'open':float(r[2]),'high':float(r[3]),'low':float(r[4]),'close':float(r[5])})
    return out
def trades(rows,start,end):
    a,b=dt.date.fromisoformat(start),dt.date.fromisoformat(end); out=[]
    closes=[r['close'] for r in rows]
    for i in range(199,len(rows)-1):
        r,n=rows[i],rows[i+1]; span=r['high']-r['low']
        sma=sum(closes[i-199:i+1])/200
        if span>0 and (r['close']-r['low'])/span<.2 and r['close']>sma and a<=n['date']<=b:
            out.append(n['close']/n['open']-1-.003)
    return out
def metrics(xs):
    gains=sum(x for x in xs if x>0); losses=-sum(x for x in xs if x<0); eq=peak=1.;dd=0
    for x in xs: eq*=1+x;peak=max(peak,eq);dd=max(dd,1-eq/peak)
    return {'trades':len(xs),'wins':sum(x>0 for x in xs),'mean_return':sum(xs)/len(xs) if xs else None,'total_return':eq-1,'profit_factor':gains/losses if losses else None,'max_drawdown':dd}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    spec=json.loads(SPEC.read_text()); assets={}
    for item in a.asset:
        name,raw=item.split('=',1);p=Path(raw);rows=load(p);parts={k:trades(rows,*v) for k,v in spec['periods'].items()};combined=parts['validation']+parts['oos']
        assets[name]={'source_sha256':sha(p),'periods':{k:metrics(v) for k,v in parts.items()},'combined_validation_oos':metrics(combined)}
    positive=sum(x['combined_validation_oos']['mean_return'] is not None and x['combined_validation_oos']['mean_return']>0 and x['periods']['oos']['total_return']>0 for x in assets.values())
    total=sum(x['combined_validation_oos']['trades'] for x in assets.values());g=sum(sum(y for y in trades(load(Path(raw)),*spec['periods'][part]) if y>0) for name,raw in (z.split('=',1) for z in a.asset) for part in ('validation','oos'));l=-sum(sum(y for y in trades(load(Path(raw)),*spec['periods'][part]) if y<0) for name,raw in (z.split('=',1) for z in a.asset) for part in ('validation','oos'))
    passed=total>=30 and positive>=3 and l>0 and g/l>=1.2
    report={'schema_version':1,'family':spec['family'],'preregistration_sha256':sha(SPEC),'optimized':False,'assets':assets,'aggregate':{'combined_trades':total,'positive_assets':positive,'profit_factor':g/l if l else None},'decision':'PASS_RESEARCH_CANDIDATE' if passed else 'REJECT_NO_TRANSFERABLE_EDGE','holdout_2025_accessed':False,'paper_authorized':False,'live_authorized':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'decision':report['decision'],'aggregate':report['aggregate'],'assets':{k:v['combined_validation_oos'] for k,v in assets.items()}},indent=2))
if __name__=='__main__':main()
