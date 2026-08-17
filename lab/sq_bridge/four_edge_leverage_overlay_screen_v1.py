#!/usr/bin/env python3
"""Frozen analytical 2x overlay on the audited four-edge stress curve."""
from __future__ import annotations
import argparse,hashlib,json,re,zipfile
from bisect import bisect_right
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET
from lab.sq_bridge.four_edge_net_mtm_audit_v1 import ACCEPTED,CAPITAL,END,START,SLEEVE,asof,load_fx
from lab.sq_bridge.sq_portfolio_daily_equity_v1 import decode
from lab.sq_bridge.sq_portfolio_ibkr_cost_fx_v1 import SCENARIOS
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];SPEC=HERE/"four_edge_leverage_overlay_preregistration_v1.json";LOCK=HERE/"four_edge_leverage_overlay_preregistration_v1.lock.json"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def base_stress_curve(sqx,fx_path):
 fx_days,fx_values=load_fx(fx_path)
 with zipfile.ZipFile(sqx) as z:
  members={n:decode(z.read(n)) for n in z.namelist() if n.endswith("dailyEquity.bin")};log=ET.fromstring(z.read("settings.xml")).find(".//PortfolioComposerLog").text or ""
 portfolio={d:p for d,p in members["Results/Portfolio/dailyEquity.bin"] if START<=d<=END};gold_name=next(n for n in members if "SGLN_" in n);gold=sorted((d,p) for d,p in members[gold_name] if d<=END);gd=[d for d,_ in gold];gp=[p for _,p in gold]
 lines=list(dict.fromkeys(x for x in log.splitlines() if "Order ACCEPTED" in x));orders=[]
 for line in lines:
  m=ACCEPTED.search(line)
  if not m:raise ValueError("order parse mismatch")
  y,mo,da=map(int,m.group(2).split("."));orders.append({"strategy":m.group(1),"date":date(y,mo,da),"price":float(m.group(3)),"size":float(m.group(4))})
 go=next(o for o in orders if o["strategy"].startswith("SGLN_"));entry_fx=asof(fx_days,fx_values,go["date"]);actual=int(SLEEVE/(go["price"]*entry_fx));c=SCENARIOS["stress"];dated={}
 for o in orders:
  if o is go:
   notional=actual*o["price"]*entry_fx;cost=2*c["uk_order_gbp"]*entry_fx+2*notional*(c["uk_bps_side"]+c["fx_bps_side"])/10000
  else:
   notional=o["price"]*o["size"];cost=2*c["us_order"]+2*notional*c["us_bps_side"]/10000
  dated[o["date"]]=dated.get(o["date"],0)+cost
 events=sorted(dated.items());ei=0;accrued=0;rows=[]
 for day in sorted(portfolio):
  while ei<len(events) and events[ei][0]<=day:accrued+=events[ei][1];ei+=1
  gi=bisect_right(gd,day)-1;sqgp=gp[gi] if gi>=0 else 0
  corrected=0 if day<go["date"] else actual*((go["price"]+sqgp/go["size"])*asof(fx_days,fx_values,day)-go["price"]*entry_fx)
  rows.append((day,CAPITAL+portfolio[day]-sqgp+corrected-accrued))
 return rows
def screen():
 s=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock["preregistration_sha256"]:raise ValueError("spec hash mismatch")
 for x in s["inputs"].values():
  if sha(ROOT/x["path"])!=x["sha256"]:raise ValueError("input hash mismatch")
 sqx=ROOT/s["inputs"]["portfolio_sqx"]["path"];fx=ROOT/s["inputs"]["ecb_fx"]["path"];base=base_stress_curve(sqx,fx);lev=s["rule"]["exposure_multiple"];rate=s["rule"]["annual_financing_rate_on_borrowed_equity"]
 equity=peak=s["rule"]["capital_usd"];minimum=equity;dd=0;prior=s["rule"]["capital_usd"];prior_day=START
 for day,value in base:
  elapsed=(day-prior_day).days
  r=value/prior-1;equity*=1+lev*r-(lev-1)*rate*elapsed/365.2425;peak=max(peak,equity);minimum=min(minimum,equity);dd=max(dd,1-equity/peak);prior=value;prior_day=day
 benchmark=json.loads((ROOT/s["inputs"]["spy_benchmark_receipt"]["path"]).read_text())["levels"]["2000"]["spy_buy_hold"]
 net=(equity/s["rule"]["capital_usd"]-1)*100;passed=net>benchmark["net_return_pct"] and dd*100<=benchmark["maximum_drawdown_pct"] and minimum>0
 return {"schema_version":1,"decision":"PASS_PROCEED_TO_EXACT_NATIVE_LEVERAGE_REBUILD" if passed else "REJECT_LEVERAGE_OVERLAY","preregistration_sha256":sha(SPEC),"optimized":False,"analytical_overlay":{"final_equity_usd":equity,"net_return_pct":net,"maximum_drawdown_pct":dd*100,"minimum_equity_usd":minimum},"spy_buy_hold":benchmark,"exact_native_rebuild_required":passed,"paper_authorized":False,"live_authorized":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--output",required=True,type=Path);a=p.parse_args();r=screen();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+"\n");print(json.dumps(r,indent=2))
if __name__=="__main__":main()
