#!/usr/bin/env python3
"""Opening-range breakout XAU COMEX, determinista i sense intrabar lookahead."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import pandas as pd


def load_5m(root):
    import duckdb
    pattern=str(root/"XAUUSD"/"tf=1m"/"year=*"/"month=*"/"data.parquet")
    sql=f"""
    WITH src AS (
      SELECT *, floor(ts/300)*300 AS bucket FROM read_parquet('{pattern}')
    ), agg AS (
      SELECT bucket, arg_min(open,ts) open, max(high) high, min(low) low,
             arg_max("close",ts) close_price, count(*) bars FROM src GROUP BY bucket
    ), local AS (
      SELECT *, to_timestamp(bucket) AT TIME ZONE 'America/New_York' ny FROM agg
    ) SELECT ny,open,high,low,close_price,bars FROM local
      WHERE CAST(ny AS TIME) BETWEEN TIME '08:20:00' AND TIME '15:45:00'
      ORDER BY ny
    """
    f=duckdb.sql(sql).df().rename(columns={"close_price":"close"}); f["ny"]=pd.to_datetime(f.ny); return f[f.bars>=3].set_index("ny")


def trades(frame,range_minutes):
    out=[]; range_bars=range_minutes//5
    for day,g in frame.groupby(frame.index.date):
        g=g.sort_index()
        # Selecció robusta per minuts des de mitjanit.
        minute=g.index.hour*60+g.index.minute; opening=g[(minute>=500)&(minute<500+range_minutes)]
        if len(opening)<max(2,range_bars-1): continue
        rh=float(opening.high.max()); rl=float(opening.low.min()); width=rh-rl
        if width<=0: continue
        after=g[minute>=500+range_minutes]
        rows=list(after.itertuples())
        signal=None
        for j,row in enumerate(rows[:-1]):
            if row.close>rh: signal=(j,1)
            elif row.close<rl: signal=(j,-1)
            if signal: break
        if not signal: continue
        j,direction=signal; entry_bar=rows[j+1]; entry=float(entry_bar.open)
        stop=rl if direction==1 else rh; risk=direction*(entry-stop)
        if risk<=0: continue
        target=entry+direction*1.5*risk; exit_price=float(rows[-1].close); reason="time"; exit_dt=rows[-1].Index
        mae=0.
        for row in rows[j+1:]:
            adverse=(entry-float(row.low))/entry if direction==1 else (float(row.high)-entry)/entry; mae=max(mae,adverse)
            stop_hit=float(row.low)<=stop if direction==1 else float(row.high)>=stop
            target_hit=float(row.high)>=target if direction==1 else float(row.low)<=target
            if stop_hit or target_hit:
                exit_price=stop if stop_hit else target; reason="stop" if stop_hit else "target"; exit_dt=row.Index; break
        out.append({"date":str(day),"direction":direction,"entry":entry,"exit":exit_price,"return":direction*(exit_price/entry-1),"risk_pct":risk/entry*100,"mae_pct":mae*100,"reason":reason,"exit_time":str(exit_dt.time())})
    return out


def metrics(rows,cost_bps):
    values=[x["return"]-cost_bps/10000 for x in rows]; curve=peak=1.; dd=0.; win=loss=0.; years={}
    for row,value in zip(rows,values):
        curve*=1+value; peak=max(peak,curve); dd=max(dd,1-curve/peak); years.setdefault(row["date"][:4],[]).append(value)
        if value>0: win+=value
        else: loss-=value
    return {"trades":len(rows),"return_pct":round((curve-1)*100,6),"profit_factor":round(win/loss,6) if loss else None,"max_drawdown_pct":round(dd*100,6),"positive_year_ratio":round(sum(math.prod(1+x for x in v)>1 for v in years.values())/len(years),6) if years else None,"median_risk_pct":round(float(pd.Series([x['risk_pct'] for x in rows]).median()),6) if rows else None,"max_mae_pct":round(max((x['mae_pct'] for x in rows),default=0),6)}


def run(root,methodology,unseal=False,finalist=None):
    if unseal and finalist is None:
        raise ValueError("HOLDOUT_REQUIRES_FROZEN_FINALIST")
    frame=load_5m(root); periods={k:v for k,v in methodology['splits'].items() if k!='holdout'}
    if unseal: periods['holdout']=methodology['splits']['holdout']
    candidates=[]
    for window in methodology['range_minutes']:
        if finalist and window!=finalist: continue
        all_trades=trades(frame,window); results={}
        for period,(start,end) in periods.items():
            sample=[x for x in all_trades if start<=x['date']<=end]
            results[period]={name:metrics(sample,bps) for name,bps in methodology['cost_roundtrip_bps'].items()}
        candidates.append({'range_minutes':window,'results':results})
    gate=methodology['gate']; eligible=[]
    for c in candidates:
        v=c['results']['validation']['stress']; o=c['results']['oos']['stress']
        if all(x['trades']>=gate['minimum_trades_each_validation_oos'] and (x['profit_factor'] or 0)>=gate['minimum_stress_profit_factor'] and x['max_drawdown_pct']<=gate['maximum_stress_drawdown_pct'] and x['positive_year_ratio']>=gate['minimum_positive_year_ratio'] for x in (v,o)): eligible.append(c['range_minutes'])
    return {'schema_version':1,'methodology_id':methodology['methodology_id'],'coverage':{'first':str(frame.index.min()),'last':str(frame.index.max()),'bars_5m':len(frame)},'holdout_unsealed':unseal,'eligible_ranges':eligible,'candidates':candidates}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True); p.add_argument('--methodology',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--unseal-holdout',action='store_true'); p.add_argument('--finalist',type=int); a=p.parse_args()
    result=run(a.root,json.loads(a.methodology.read_text()),a.unseal_holdout,a.finalist); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
