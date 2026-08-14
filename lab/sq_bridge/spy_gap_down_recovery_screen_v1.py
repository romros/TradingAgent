#!/usr/bin/env python3
"""Frozen observable SPY gap-down recovery test with gated 2024 OOS."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent; SPEC=HERE/"spy_gap_down_recovery_preregistration_v1.json"; LOCK=HERE/"spy_gap_down_recovery_preregistration_v1.lock.json"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def spec():
 s=json.loads(SPEC.read_text()); lock=json.loads(LOCK.read_text())
 if s["status"]!="FROZEN_BEFORE_PERFORMANCE" or sha(SPEC)!=lock["preregistration_sha256"] or lock["oos_2024_accessed"] is not False: raise ValueError("lock mismatch")
 return s
def prices(path,allow):
 if "2025" in Path(path).name: raise ValueError("2025 refused")
 out=[]
 with Path(path).open(newline="") as h:
  for r in csv.reader(h):
   if not r or r[0].lower()=="date": continue
   d=r[0].replace(".","-")
   if d>("2024-12-31" if allow else "2023-12-31"): continue
   o=2 if len(r)>=7 and ":" in r[1] else 1; out.append({"date":d,"open":float(r[o]),"close":float(r[o+3])})
 return sorted(out,key=lambda x:x["date"])
def trades(rows,s,bounds):
 out=[]
 for i in range(1,len(rows)):
  r=rows[i]; gap=r["open"]/rows[i-1]["close"]-1
  if bounds[0]<=r["date"]<=bounds[1] and gap<=s["rule"]["maximum_open_vs_previous_close"]:
   out.append({"date":r["date"],"gap":gap,"return":r["close"]/r["open"]-1-s["rule"]["roundtrip_cost_bps"]/10000})
 return out
def metrics(rows):
 eq=peak=1.;dd=w=l=0.; years={}; vals=[]
 for r in rows:
  v=r["return"]; vals.append(v);eq*=1+v;peak=max(peak,eq);dd=max(dd,1-eq/peak);w+=max(v,0);l+=max(-v,0);years[r["date"][:4]]=years.get(r["date"][:4],1.)*(1+v)
 mean=sum(vals)/len(vals) if vals else None; var=sum((v-mean)**2 for v in vals)/len(vals) if vals else None
 return {"trades":len(rows),"net_return":eq-1,"profit_factor":w/l if l else None,"maximum_drawdown":dd,"mean_trade_return":mean,"t_stat":mean/math.sqrt(var/len(vals)) if var and vals else None,"calendar_year_returns":{k:v-1 for k,v in sorted(years.items())},"positive_calendar_years":sum(v>1 for v in years.values())}
def passed(m,g): return bool(m["trades"]>=g["minimum_trades"] and m["net_return"]>g["minimum_net_return"] and m["profit_factor"] is not None and m["profit_factor"]>=g["minimum_profit_factor"] and m["positive_calendar_years"]>=g["positive_calendar_years_required"] and m["maximum_drawdown"]<=g["maximum_drawdown"])
def screen(path):
 s=spec(); pre=prices(path,False); train=metrics(trades(pre,s,s["periods"]["train"])); val=metrics(trades(pre,s,s["periods"]["validation"])); ok=passed(val,s["validation_gate"])
 result={"schema_version":1,"campaign_id":s["campaign_id"],"preregistration_sha256":sha(SPEC),"source_sha256":sha(path),"train":train,"validation":val,"validation_gate_passed":ok,"decision":"PASS_VALIDATION_OPEN_OOS" if ok else "REJECT_VALIDATION","oos_2024_accessed":False,"holdout_2025_accessed":False,"optimized":False,"paper_authorized":False,"live_authorized":False}
 if ok: result["oos"]=metrics(trades(prices(path,True),s,s["periods"]["oos"]));result["oos_2024_accessed"]=True
 return result
def main():
 a=argparse.ArgumentParser();a.add_argument("--source",type=Path,required=True);a.add_argument("--output",type=Path,required=True);x=a.parse_args();r=screen(x.source);x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(json.dumps(r,indent=2)+"\n");print(json.dumps(r,indent=2))
if __name__=="__main__":main()
