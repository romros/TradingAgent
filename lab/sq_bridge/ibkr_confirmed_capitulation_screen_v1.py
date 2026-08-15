#!/usr/bin/env python3
"""Frozen cross-asset confirmed-capitulation screen on canonical D1 data."""
from __future__ import annotations
import argparse, csv, hashlib, itertools, json, math
from datetime import date
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=HERE/'ibkr_confirmed_capitulation_preregistration_v1.json'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    rows=[]
    with path.open(newline='',encoding='utf-8-sig') as stream:
        for raw in csv.reader(stream):
            if raw and raw[0].lower()=='date': continue
            if not raw: continue
            d=date.fromisoformat(raw[0].replace('.','-'))
            if d.year>=2025: raise ValueError('post-2024 data sealed')
            if '.' in raw[0]: o,h,l,c=map(float,raw[2:6])
            else: o,h,l,c=map(float,raw[1:5])
            rows.append((d,o,h,l,c))
    if not rows or any(a[0]>=b[0] for a,b in zip(rows,rows[1:])): raise ValueError('invalid chronology')
    return rows
def trades(rows,p):
    z,recovery,hold,regime=p; closes=[r[4] for r in rows]; returns=[None]+[closes[i]/closes[i-1]-1 for i in range(1,len(rows))]
    out=[]; last_exit=-1
    for drop in range(200,len(rows)-hold-2):
        hist=returns[drop-20:drop]; mean=sum(hist)/20; sigma=math.sqrt(sum((x-mean)**2 for x in hist)/20)
        if sigma<=0 or returns[drop] > -z*sigma: continue
        if regime and closes[drop-1] <= sum(closes[drop-200:drop])/200: continue
        confirm=drop+1; loss=closes[drop-1]-closes[drop]
        if loss<=0 or closes[confirm]-closes[drop] < recovery*loss: continue
        entry=confirm+1; exit_i=entry+hold
        if entry<=last_exit or exit_i>=len(rows): continue
        out.append({'entry':rows[entry][0],'return':rows[exit_i][1]/rows[entry][1]-1-.003})
        last_exit=exit_i
    return out
def metrics(ts):
    rs=[x['return'] for x in ts]; eq=peak=1.; dd=0.; gp=gl=0.
    for r in rs:
        eq*=1+r; peak=max(peak,eq); dd=max(dd,1-eq/peak); gp+=max(r,0); gl+=max(-r,0)
    return {'trades':len(rs),'return':eq-1,'profit_factor':gp/gl if gl else None,'max_drawdown':dd}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--asset',action='append',required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    spec=json.loads(SPEC.read_text()); paths=dict(x.split('=',1) for x in a.asset)
    if set(paths)!=set(spec['assets']): raise ValueError('frozen universe required')
    frames={k:load(Path(v)) for k,v in paths.items()}; g=spec['grid']; variants=list(itertools.product(g['drop_z'],g['recovery_fraction'],g['holding_days'],g['regime_sma200']))
    periods={k:tuple(map(date.fromisoformat,v)) for k,v in spec['periods'].items()}; report=[]
    for p in variants:
        pooled=[]; by_asset={}
        for asset,rows in frames.items():
            found=trades(rows,p); chosen=[x for x in found if periods['validation'][0]<=x['entry']<=periods['oos'][1]]; by_asset[asset]=metrics(chosen); pooled+=chosen
        m=metrics(sorted(pooled,key=lambda x:x['entry'])); gate=spec['variant_gate']; passed=(m['trades']>=gate['minimum_trades_combined'] and (m['profit_factor'] or 0)>=gate['minimum_profit_factor'] and m['return']>0 and m['max_drawdown']<=gate['maximum_drawdown'])
        report.append({'parameters':{'drop_z':p[0],'recovery_fraction':p[1],'holding_days':p[2],'regime_sma200':p[3]},'combined_validation_oos':m,'by_asset':by_asset,'pass':passed})
    central=spec['central_variant']; central_row=next(x for x in report if x['parameters']==central); positive=sum(x['return']>0 for x in central_row['by_asset'].values()); passing=sum(x['pass'] for x in report)
    fg=spec['family_gate']; decision='PASS_FAMILY_TO_NATIVE_SQ' if passing>=fg['minimum_passing_variants'] and positive>=fg['minimum_assets_positive_central_variant'] else 'REJECT_FAMILY'
    result={'schema_version':1,'decision':decision,'preregistration_sha256':sha(SPEC),'variants':len(report),'passing_variants':passing,'central_positive_assets':positive,'central_variant':central_row,'results':report,'optimized':False,'post_2024_accessed':False}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps({k:result[k] for k in ('decision','variants','passing_variants','central_positive_assets')},indent=2))
if __name__=='__main__': main()
