#!/usr/bin/env python3
"""Frozen same-assets buy-and-hold comparator for the four-edge portfolio."""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from bisect import bisect_right
from datetime import date
from pathlib import Path
try:
    from .four_edge_net_mtm_audit_v1 import drawdown, load_fx, asof
    from .sq_portfolio_ibkr_cost_fx_v1 import SCENARIOS
except ImportError:
    from four_edge_net_mtm_audit_v1 import drawdown, load_fx, asof
    from sq_portfolio_ibkr_cost_fx_v1 import SCENARIOS

START, END = date(2022,1,1), date(2024,12,31)
CAPITAL, RATE = 2000.0, .08
ACTIVE_RETURN, ACTIVE_DD = 56.041808, 15.915973
EXPECTED = {
 "cat":"9d043cd5a9a9024007b340b8e76477b0aeabcebb9bae59b0e4ec2930be7ac73e",
 "msft":"c28f9851347d9f854e6b5b85f193a015adb699228e44010718a47458801e89b1",
 "jpm":"1b5bc1a71c5d330cb4933ec0dd6f2e3ef9f3a3ca5053bd2b4b78ca48d0179270",
 "sgln":"25008847d1f9c8be10b9d60a0a52306ab46134febe3b63d720914fef2c28d713",
 "fx":"f95006726de866df21bea8ca0c3a1e7f9d082600b57d04199ab37201b7b48e21"}
# Actual tradable opens on the first session. Adjusted prices are rescaled to
# these levels, preserving total return without manufacturing extra shares.
NOMINAL_OPEN = {"cat":207.006, "msft":335.35, "jpm":159.747}
NOMINAL_PROVENANCE = {
 "cat":"CATUSUSD_CANONICAL_D1_2017_2025.csv sha256 9aa5e9f6...",
 "msft":"SQ export MSFT-D1-No Session.csv sha256 b19c15a9...",
 "jpm":"JPMUSUSD_CANONICAL_D1_2017_2024.csv sha256 4c75a75b..."}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(path, header=True, pence=False):
 rows=[]
 with Path(path).open(newline='') as f:
  src=csv.DictReader(f) if header else csv.reader(f)
  for r in src:
   d=date.fromisoformat(r['date']) if header else date.fromisoformat(r[0].replace('.','-'))
   if START<=d<=END:
    o,c=(float(r['open']),float(r['close'])) if header else (float(r[2]),float(r[5]))
    rows.append((d,o/(100 if pence else 1),c/(100 if pence else 1)))
 if not rows or rows[0][0].year!=2022 or rows[-1][0]!=END: raise ValueError('incomplete sealed series')
 return rows
def prior(rows, day):
 ds=[x[0] for x in rows]; i=bisect_right(ds,day)-1
 return rows[i][2] if i>=0 else None

def scenario(paths, fx_path, budget, cost):
 fx_days,fx_values=load_fx(fx_path)
 series={"cat":load(paths['cat']),"msft":load(paths['msft']),"jpm":load(paths['jpm']),"sgln":load(paths['sgln'],False,True)}
 for key,nominal in NOMINAL_OPEN.items():
  factor=nominal/series[key][0][1]
  series[key]=[(d,o*factor,c*factor) for d,o,c in series[key]]
 cash=CAPITAL; legs={}; total_cost=0.; entries={}
 for key,rows in series.items():
  d,o=rows[0][0],rows[0][1]
  if key=='sgln':
   rate=asof(fx_days,fx_values,d); unit=o*rate; shares=math.floor(budget/unit)
   entry=shares*unit; fee=cost['uk_order_gbp']*rate+entry*(cost['uk_bps_side']+cost['fx_bps_side'])/10000
  else:
   shares=math.floor(budget/o); entry=shares*o; fee=cost['us_order']+entry*cost['us_bps_side']/10000
  if shares<1: raise ValueError(f'unaffordable {key}')
  entries[d]=entries.get(d,0.)+entry+fee; total_cost+=fee
  legs[key]={"shares":shares,"entry_usd":entry,"entry_cost":fee,"entry_date":d.isoformat()}
 days=sorted(set(d for rows in series.values() for d,_,_ in rows)); curve=[]; financing=0.; prev=days[0]
 for day in days:
  charge=max(-cash,0)*RATE*(day-prev).days/365.2425; cash-=charge; financing+=charge
  cash-=entries.get(day,0.)
  value=0.
  for key,rows in series.items():
   close=prior(rows,day)
   if close is None or day < date.fromisoformat(legs[key]['entry_date']): continue
   if key=='sgln': close*=asof(fx_days,fx_values,day)
   value+=legs[key]['shares']*close
  curve.append((day,cash+value)); prev=day
 # Conservatively charge terminal liquidation costs on the final mark.
 exit_cost=0.
 for key,rows in series.items():
  close=rows[-1][2]; shares=legs[key]['shares']
  if key=='sgln':
   rate=asof(fx_days,fx_values,END); notional=shares*close*rate
   exit_cost+=cost['uk_order_gbp']*rate+notional*(cost['uk_bps_side']+cost['fx_bps_side'])/10000
  else:
   notional=shares*close; exit_cost+=cost['us_order']+notional*cost['us_bps_side']/10000
 total_cost+=exit_cost; curve[-1]=(curve[-1][0],curve[-1][1]-exit_cost)
 final=curve[-1][1]
 years=(END-START).days/365.2425
 return {"budget_per_asset_usd":budget,"final_equity_usd":round(final,6),"return_pct":round((final/CAPITAL-1)*100,6),
  "cagr_pct":round(((final/CAPITAL)**(1/years)-1)*100,6),
  "costs_usd":round(total_cost,6),"financing_usd":round(financing,6),"minimum_equity_usd":round(min(v for _,v in curve),6),
  "legs":legs,**drawdown(curve)}

def run(paths,fx):
 for k,p in {**paths,'fx':fx}.items():
  if sha(p)!=EXPECTED[k]: raise ValueError(f'frozen {k} hash mismatch')
 stress=SCENARIOS['stress']; unlevered=scenario(paths,fx,500,stress); matched=scenario(paths,fx,1000,stress)
 def compare(b): return {"active_minus_buy_hold_return_points":round(ACTIVE_RETURN-b['return_pct'],6),
  "active_to_buy_hold_drawdown_ratio":round(ACTIVE_DD/b['daily_mtm_max_drawdown_pct'],6),
  "return_pass":ACTIVE_RETURN>b['return_pct'],"drawdown_pass":ACTIVE_DD<=b['daily_mtm_max_drawdown_pct']}
 years=(END-START).days/365.2425
 return {"schema_version":1,"decision":"PASS_ACTIVE_BEATS_BOTH_SAME_ASSET_BENCHMARKS" if all(compare(x)['return_pass'] and compare(x)['drawdown_pass'] for x in (unlevered,matched)) else "PASS_UNLEVERED_AND_RISK_FAIL_MAX_RETURN_MATCHED_EXPOSURE",
  "period":f"{START}/{END}","active":{"return_pct":ACTIVE_RETURN,"cagr_pct":round(((1+ACTIVE_RETURN/100)**(1/years)-1)*100,6),"daily_mtm_max_drawdown_pct":ACTIVE_DD},
  "same_assets_buy_hold_unlevered":unlevered,"same_assets_buy_hold_exposure_matched":matched,
  "comparison_unlevered":compare(unlevered),"comparison_exposure_matched":compare(matched),
  "nominal_entry_open_provenance":NOMINAL_PROVENANCE,
  "limitations":["Adjusted total-return series are rescaled to nominal first-session opens so whole-share sizing is executable and dividends remain represented.","Exposure-matched buy-and-hold pays 8% on negative cash for the entire holding period.","No paper or live trading is authorized."],
  "post_2024_accessed":False,"paper_authorized":False,"live_authorized":False}
def main():
 p=argparse.ArgumentParser()
 for k in ('cat','msft','jpm','sgln','fx'):p.add_argument('--'+k,required=True,type=Path)
 p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=run({k:getattr(a,k) for k in ('cat','msft','jpm','sgln')},a.fx);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
