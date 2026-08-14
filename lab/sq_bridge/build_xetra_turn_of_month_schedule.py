#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from packages.strategy.turn_of_month import build_schedule
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--calendar',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();source=json.loads(a.calendar.read_text());year=int(source['year']);closed={dt.date.fromisoformat(x) for x in source['non_trading_days']};day=dt.date(year,1,1);sessions=[]
 while day.year==year:
  if day.weekday()<5 and day not in closed:sessions.append(day)
  day+=dt.timedelta(days=1)
 actions=build_schedule(sessions);report={'schema_version':1,'exchange':source['exchange'],'year':year,'calendar_sha256':hashlib.sha256(a.calendar.read_bytes()).hexdigest(),'sessions':len(sessions),'first_session':sessions[0].isoformat(),'last_session':sessions[-1].isoformat(),'performance_accessed':False,'actions':[{'date':x.session.isoformat(),'action':x.action,'cycle':x.cycle,'reason':x.reason,'idempotency_key':f'turn_of_month:{x.cycle}:{x.action}'} for x in actions],'paper_mode':'shadow_only','orders_authorized':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'sessions':len(sessions),'actions':len(actions),'next_actions':[x for x in report['actions'] if x['date']>='2026-08-14'][:4]},indent=2))
if __name__=='__main__':main()
