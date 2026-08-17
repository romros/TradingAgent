#!/usr/bin/env python3
"""Frozen 1.5x SPY SMA200 timing screen versus passive SPY."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,statistics
from pathlib import Path

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
SPEC=HERE/"spy_sma200_levered_preregistration_v1.json"; LOCK=HERE/"spy_sma200_levered_preregistration_v1.lock.json"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(path):
 out=[]
 with Path(path).open(newline="") as f:
  for r in csv.reader(f):
   if not r or r[0].lower()=="date": continue
   off=2 if len(r)>6 and ":" in r[1] else 1
   day=r[0].replace(".","-")
   if day<="2024-12-31": out.append({"date":day,"open":float(r[off]),"close":float(r[off+3])})
 return sorted(out,key=lambda x:x["date"])
def metrics(rows,key):
 eq=peak=1.; dd=0.; vals=[]
 for r in rows:
  v=r[key]; vals.append(v); eq*=1+v; peak=max(peak,eq); dd=max(dd,1-eq/peak)
 years=len(rows)/252
 return {"sessions":len(rows),"net_return":eq-1,"cagr":eq**(1/years)-1 if years else None,"maximum_drawdown":dd,
  "annualized_sharpe":statistics.mean(vals)/statistics.stdev(vals)*math.sqrt(252) if len(vals)>1 and statistics.stdev(vals)>0 else None}
def engine(rows,spec):
 rule=spec["rule"]; old=0.; out=[]; closes=[r["close"] for r in rows]
 for i in range(200,len(rows)):
  prior=rows[i-1]; row=rows[i]; sma=sum(closes[i-200:i])/200
  new=rule["risk_on_exposure"] if prior["close"]>sma else rule["risk_off_exposure"]
  gap=row["open"]/prior["close"]-1; intraday=row["close"]/row["open"]-1
  gross=(1+old*gap)*(1+new*intraday)-1
  cost=abs(new-old)*rule["one_way_turnover_cost_bps"]/10000
  borrow=max(old-1,0)*rule["annual_borrow_rate_on_exposure_above_one"]/252
  out.append({"date":row["date"],"strategy_return":gross-cost-borrow,"buy_hold_return":row["close"]/prior["close"]-1,"exposure":new})
  old=new
 return out
def screen():
 spec=json.loads(SPEC.read_text()); lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock["preregistration_sha256"]: raise ValueError("preregistration hash mismatch")
 source=ROOT/spec["source"]; allrows=engine(load(source),spec); periods={}
 for name,b in spec["periods"].items():
  rows=[r for r in allrows if b[0]<=r["date"]<=b[1]]
  periods[name]={"strategy":metrics(rows,"strategy_return"),"buy_and_hold":metrics(rows,"buy_hold_return"),
   "average_exposure":statistics.mean(r["exposure"] for r in rows)}
 passed=all(periods[p]["strategy"]["net_return"]>periods[p]["buy_and_hold"]["net_return"] for p in ("train","validation","oos_2024")) and all(periods[p]["strategy"]["maximum_drawdown"]<=periods[p]["buy_and_hold"]["maximum_drawdown"] for p in ("validation","oos_2024"))
 return {"schema_version":1,"decision":"PASS_RETURN_AND_DRAWDOWN_GATE" if passed else "REJECT_RETURN_AND_DRAWDOWN_GATE",
  "preregistration_sha256":sha(SPEC),"source_sha256":sha(source),"optimized":False,"periods":periods,
  "paper_authorized":False,"live_authorized":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--output",required=True,type=Path);a=p.parse_args();r=screen();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+"\n");print(json.dumps(r,indent=2))
if __name__=="__main__":main()
