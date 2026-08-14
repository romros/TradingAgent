#!/usr/bin/env python3
"""Export blinded pre-2025 D1 projections for XAUUSD, EURUSD and SPX."""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path
import duckdb

ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'data/ibkr_sq_v2/cross_asset_sources'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name, rows):
    p=OUT/f'{name}_D1_2017_2024.csv'; p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        for d,o,h,l,c,v,n in rows: w.writerow([str(d).replace('-','.'),'00:00',f'{o:.6f}',f'{h:.6f}',f'{l:.6f}',f'{c:.6f}',f'{v:.6f}'])
    return {'path':str(p),'rows':len(rows),'first':str(rows[0][0]),'last':str(rows[-1][0]),'sha256':sha(p),'maximum_date':'2024-12-31'}
def fx(symbol):
    pattern=f'/mnt/volume-SQ/dev/BrokerageService/datafiles/historical_parquet/{symbol}/tf=1m/year=*/month=*/data.parquet'
    return duckdb.sql(f"""WITH x AS (SELECT *,timezone('America/New_York',to_timestamp(ts)) local_ts FROM read_parquet('{pattern}') WHERE year BETWEEN 2017 AND 2024), y AS (SELECT CASE WHEN CAST(local_ts AS TIME)>=TIME '17:00' THEN CAST(local_ts AS DATE)+1 ELSE CAST(local_ts AS DATE) END d,count(*) n,arg_min(open,ts)o,max(high)h,min(low)l,arg_max(close,ts)c,sum(volume)v FROM x GROUP BY 1) SELECT d,o,h,l,c,v,n FROM y WHERE dayofweek(d) BETWEEN 1 AND 5 AND n>=1000 ORDER BY d""").fetchall()
def spx():
    p=ROOT/'lab/out/market_sources/sp_m1_dukas_utc_2012_2026.parquet'
    return duckdb.sql(f"""WITH x AS (SELECT *,timezone('America/New_York',to_timestamp(ts)) local_ts FROM read_parquet('{p}') WHERE ts<epoch(TIMESTAMP '2025-01-01')), y AS (SELECT CAST(local_ts AS DATE)d,count(*)n,arg_min(open,ts)o,max(high)h,min(low)l,arg_max(close,ts)c,sum(volume)v FROM x WHERE CAST(local_ts AS TIME)>=TIME '09:30' AND CAST(local_ts AS TIME)<TIME '16:00' GROUP BY 1) SELECT d,o,h,l,c,v,n FROM y WHERE d>=DATE '2017-01-01' AND n>=350 ORDER BY d""").fetchall()
def main():
    result={s:write(s,fx(s)) for s in ('EURUSD','XAUUSD')}; result['SPX']=write('SPX',spx()); result['performance_accessed']=False; result['holdout_2025_accessed']=False
    (OUT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__':main()
