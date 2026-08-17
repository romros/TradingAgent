#!/usr/bin/env python3
"""Performance-blind point-in-time SEC calendar for the expanded gap study."""
from __future__ import annotations

import argparse, csv, hashlib, json
from bisect import bisect_left, bisect_right
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

NY=ZoneInfo("America/New_York")
CIK_TO_ASSET={
 "0000320193":"AAPL","0001018724":"AMZN","0001652044":"GOOG","0001326801":"META",
 "0001045810":"NVDA","0000019617":"JPM","0000021344":"KO","0000315189":"DE",
 "0000200406":"JNJ","0000100885":"UNP","0000034088":"XOM","0000789019":"MSFT",
 "0000077476":"PEP","0000018230":"CAT","0001065280":"NFLX","0001318605":"TSLA"}

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()
def market_dates(path:Path)->list[date]:
 with path.open(newline="") as s:
  first=s.readline(); s.seek(0)
  values=[date.fromisoformat(r["date"]) for r in csv.DictReader(s)] if first.lower().startswith("date,") else [date.fromisoformat(x.split(",",1)[0].replace(".","-")) for x in s if x.strip()]
 return sorted(d for d in values if date(2017,1,1)<=d<=date(2024,12,31))
def columns(doc:dict)->dict: return doc["filings"]["recent"] if "filings" in doc else doc
def rows(cols:dict):
 keys=("accessionNumber","acceptanceDateTime","filingDate","form","items")
 for vals in zip(*(cols[k] for k in keys)): yield dict(zip(keys,vals))

def preflight(sec_roots:list[Path], price_paths:dict[str,Path])->dict:
 if set(price_paths)!=set(CIK_TO_ASSET.values()): raise ValueError("frozen sixteen-asset universe required")
 assets={}; events=[]
 for cik,asset in CIK_TO_ASSET.items():
  candidates=[]
  for root in sec_roots: candidates.extend(sorted(root.glob(f"CIK{cik}*.json")))
  unique={p.resolve():p for p in candidates}
  main=[p for p in unique.values() if p.name==f"CIK{cik}.json"]
  if len(main)!=1: raise ValueError(f"exactly one main SEC file required for {asset}: {main}")
  docs=[]; hashes=[]
  for p in unique.values():
   doc=json.loads(p.read_text()); docs.append(doc); hashes.append({"path":str(p),"sha256":sha(p)})
  sessions=market_dates(price_paths[asset]); observed={}
  for doc in docs:
   for filing in rows(columns(doc)):
    if filing["form"]=="8-K" and "2.02" in filing["items"]: observed[filing["accessionNumber"]]=filing
  own=[]
  for filing in observed.values():
   accepted=datetime.fromisoformat(filing["acceptanceDateTime"].replace("Z","+00:00")).astimezone(NY)
   if not date(2017,1,1)<=accepted.date()<=date(2024,12,31): continue
   ri=bisect_left(sessions,accepted.date()) if accepted.date() in sessions and accepted.time()<time(16) else bisect_right(sessions,accepted.date())
   if ri+6>=len(sessions): continue
   event={"asset":asset,"accession":filing["accessionNumber"],"accepted_utc":filing["acceptanceDateTime"],
    "accepted_ny":accepted.isoformat(),"reaction_session":str(sessions[ri]),"entry_session":str(sessions[ri+1])}
   own.append(event); events.append(event)
  assets[asset]={"market_path":str(price_paths[asset]),"market_sha256":sha(price_paths[asset]),
   "first_market_date":str(sessions[0]),"last_market_date":str(sessions[-1]),"item_202_events":len(own),"sec_sources":sorted(hashes,key=lambda x:x["path"])}
 events.sort(key=lambda x:(x["reaction_session"],x["asset"],x["accession"]))
 return {"schema_version":2,"decision":"PASS_EXPANDED_SEC_POINT_IN_TIME_CALENDAR_PREFLIGHT","performance_accessed":False,
  "universe":sorted(price_paths),"events":events,"event_counts":{n:sum(a<=e["reaction_session"]<=b for e in events) for n,(a,b) in
   {"train":("2017-01-01","2021-12-31"),"validation":("2022-01-01","2023-12-31"),"oos_2024":("2024-01-01","2024-12-31")}.items()},"assets":assets}

def main():
 p=argparse.ArgumentParser(); p.add_argument("--sec-root",action="append",required=True,type=Path); p.add_argument("--asset",action="append",required=True); p.add_argument("--output",required=True,type=Path); a=p.parse_args()
 paths={n:Path(v) for n,v in (x.split("=",1) for x in a.asset)}; result=preflight(a.sec_root,paths)
 a.output.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps({"event_counts":result["event_counts"],"assets":{k:v["item_202_events"] for k,v in result["assets"].items()}},indent=2))
if __name__=="__main__": main()
