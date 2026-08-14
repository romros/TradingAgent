#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from packages.strategy.turn_of_month import build_schedule
def sessions(path):
 out=[]
 for line in path.read_text().splitlines():
  if line.strip():out.append(dt.datetime.strptime(line.split(',')[0],'%Y.%m.%d').date())
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--sessions-csv',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();ss=sessions(a.sessions_csv);schedule=build_schedule(ss);report={'schema_version':1,'strategy':'sxr8_turn_of_month_last1_first3','instrument':{'symbol':'SXR8','isin':'IE00B5BMR087','contract_verified':False},'source_sha256':hashlib.sha256(a.sessions_csv.read_bytes()).hexdigest(),'first_session':ss[0].isoformat(),'last_session':ss[-1].isoformat(),'actions':[{'date':x.session.isoformat(),'action':x.action,'cycle':x.cycle,'reason':x.reason,'idempotency_key':f'turn_of_month:{x.cycle}:{x.action}'} for x in schedule], 'paper_authorized':False,'live_authorized':False}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'actions':len(schedule),'first':report['actions'][0],'last':report['actions'][-1]},indent=2))
if __name__=='__main__':main()
