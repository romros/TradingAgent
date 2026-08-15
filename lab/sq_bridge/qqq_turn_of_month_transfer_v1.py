#!/usr/bin/env python3
import argparse,datetime as dt,json
from pathlib import Path
from lab.sq_bridge.turn_of_month_screen_v1 import load,trades,metrics,sha
H=Path(__file__).resolve().parent;S=H/'qqq_turn_of_month_transfer_preregistration_v1.json';L=H/'qqq_turn_of_month_transfer_preregistration_v1.lock.json'
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text());assert sha(S)==l['preregistration_sha256'];f=load(a.source);rows={k:trades(f,*map(dt.date.fromisoformat,v)) for k,v in s['periods'].items()};net=lambda x:[(d,r-.0025) for d,r in x];m={k:metrics(net(v)) for k,v in rows.items()};c=metrics(net(rows['validation']+rows['oos_2024']));g=s['gates'];ok=all(m[k]['total_return']>0 for k in m) and (c['profit_factor'] or 0)>=g['combined_minimum_profit_factor'] and (c['monthly_sharpe'] or -999)>=g['combined_minimum_monthly_sharpe'] and c['max_drawdown']<=g['combined_maximum_drawdown'];r={'decision':'PASS_OPEN_RECENT_HOLDOUT' if ok else 'REJECT_TRANSFER','periods_25bps':m,'validation_oos_25bps':c,'source_sha256':sha(a.source),'holdout_2025_plus_accessed':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
