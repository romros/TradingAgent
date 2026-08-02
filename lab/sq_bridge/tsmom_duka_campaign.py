#!/usr/bin/env python3
"""Campanya TSMOM preregistrada sobre Parquet Dukascopy, sense SQ ni Yahoo."""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np, pandas as pd


def load_daily(root: Path, symbol: str) -> pd.DataFrame:
    import duckdb
    pattern=str(root/symbol/"tf=1m"/"year=*"/"month=*"/"data.parquet")
    # 17:00 NY inicia la sessió etiquetada com el dia següent. La conversió IANA
    # incorpora DST, a diferència d'un offset UTC fix.
    sql=f"""
    WITH bars AS (
      SELECT *, (to_timestamp(ts) AT TIME ZONE 'America/New_York') AS ny
      FROM read_parquet('{pattern}')
    ), labelled AS (
      SELECT *, CAST(ny + INTERVAL '7 hours' AS DATE) AS session_date
      FROM bars
    )
    SELECT session_date,
      arg_min(open, ts) AS open, max(high) AS high, min(low) AS low,
      arg_max(close, ts) AS close, count(*) AS bars
    FROM labelled GROUP BY session_date ORDER BY session_date
    """
    frame=duckdb.sql(sql).df().set_index("session_date"); frame.index=pd.to_datetime(frame.index)
    return frame[(frame.close>0)&(frame.bars>=60)]


def model_returns(frame, lookback, costs, target=.10, leg_budget=.5):
    ret=frame.close.pct_change(); vol=ret.rolling(20).std()*math.sqrt(252)
    exposure=(target/vol).clip(upper=1.0)*leg_budget
    if lookback=="ensemble":
        votes=sum(np.sign(frame.close/frame.close.shift(n)-1) for n in (21,63,126,252))
        direction=np.sign(votes)
    else: direction=np.sign(frame.close/frame.close.shift(int(lookback))-1)
    desired_direction=direction.shift(1).fillna(0)
    desired_exposure=exposure.shift(1).fillna(0)
    held=[]; current=0.0; previous_sign=0.0
    for sign,size in zip(desired_direction,desired_exposure):
        if sign != previous_sign:
            current=float(sign*size) if sign else 0.0
            previous_sign=float(sign)
        held.append(current)
    position=pd.Series(held,index=frame.index)
    changes=np.sign(position).ne(np.sign(position.shift(1).fillna(0))) & position.ne(0)
    gross=position*ret.fillna(0)
    result={"gross":gross,"position":position,"changes":changes}
    for name,spec in costs.items():
        entry=changes.astype(float)*position.abs()*spec["entry_bps"]/10000
        elapsed_days=frame.index.to_series().diff().dt.total_seconds().div(86400).fillna(0).clip(upper=4)
        rollover=position.abs()*spec["annual_rollover_pct"]/100*elapsed_days/365.25
        result[name]=gross-entry-rollover
    return result


def metrics(series):
    s=series.dropna(); equity=(1+s).cumprod(); peak=equity.cummax(); dd=1-equity/peak
    annual=(equity.iloc[-1]**(252/len(s))-1) if len(s) and equity.iloc[-1]>0 else -1
    vol=s.std()*math.sqrt(252); sharpe=s.mean()/s.std()*math.sqrt(252) if s.std()>0 else None
    years=s.groupby(s.index.year).apply(lambda x:(1+x).prod()-1)
    return {"days":len(s),"total_return_pct":round(((equity.iloc[-1]-1) if len(equity) else 0)*100,6),
      "annual_return_pct":round(annual*100,6),"annual_volatility_pct":round(vol*100,6),
      "sharpe":round(float(sharpe),6) if sharpe is not None else None,
      "max_drawdown_pct":round(float(dd.max() if len(dd) else 0)*100,6),
      "positive_year_ratio":round(float((years>0).mean()),6) if len(years) else None,
      "year_returns_pct":{str(k):round(float(v)*100,4) for k,v in years.items()}}


def campaign(root: Path, methodology: dict, unseal=False, finalist=None):
    if unseal and finalist is None:
        raise ValueError("HOLDOUT_REQUIRES_FROZEN_FINALIST")
    costs={k:{"entry_bps":methodology["costs"]["opening_only_bps"][k],"annual_rollover_pct":methodology["costs"]["annual_rollover_both_sides_pct"][k]} for k in ("base","conservative","stress")}
    frames={s:load_daily(root,s) for s in methodology["data"]["symbols"]}; models=[21,63,126,252,"ensemble"]
    periods={k:v for k,v in methodology["splits"].items() if k in {"train","validation","oos"}}
    if unseal: periods["holdout"]=methodology["splits"]["holdout"]
    rows=[]
    for model in models:
        if finalist is not None and str(model)!=str(finalist): continue
        legs={s:model_returns(f,model,costs) for s,f in frames.items()}; common=sorted(set.intersection(*(set(v["gross"].index) for v in legs.values())))
        combined={name:pd.concat([legs[s][name].reindex(common) for s in legs],axis=1).sum(axis=1) for name in ("gross","base","conservative","stress")}
        period_results={}
        for period,(start,end) in periods.items(): period_results[period]={name:metrics(series.loc[start:end]) for name,series in combined.items()}
        rows.append({"model":str(model),"results":period_results,"position_changes":{s:int(legs[s]["changes"].sum()) for s in legs}})
    gate=methodology["selection_gate"]
    eligible=[]
    for row in rows:
        v=row["results"]["validation"]["stress"]; o=row["results"]["oos"]["stress"]
        if v["sharpe"]>=gate["minimum_validation_sharpe_stress"] and o["sharpe"]>=gate["minimum_oos_sharpe_stress"] and o["max_drawdown_pct"]<=gate["maximum_oos_drawdown_stress_pct"] and o["positive_year_ratio"]>=gate["minimum_positive_oos_year_ratio"] and o["total_return_pct"]>0: eligible.append(row["model"])
    hashes={s:hashlib.sha256("\n".join(f"{i.date()},{r.close}" for i,r in f.iterrows()).encode()).hexdigest() for s,f in frames.items()}
    return {"schema_version":1,"methodology_id":methodology["methodology_id"],"daily_close_hashes":hashes,
      "coverage":{s:{"first":str(f.index.min().date()),"last":str(f.index.max().date()),"days":len(f)} for s,f in frames.items()},
      "holdout_unsealed":unseal,"eligible_models":eligible,"models":rows}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,required=True); p.add_argument("--methodology",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--unseal-holdout",action="store_true"); p.add_argument("--finalist"); a=p.parse_args()
    result=campaign(a.root,json.loads(a.methodology.read_text()),a.unseal_holdout,a.finalist); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"coverage":result["coverage"],"eligible_models":result["eligible_models"],"models":[{"model":x["model"],"validation":x["results"]["validation"]["stress"],"oos":x["results"]["oos"]["stress"]} for x in result["models"]]},indent=2))
if __name__=="__main__": main()
