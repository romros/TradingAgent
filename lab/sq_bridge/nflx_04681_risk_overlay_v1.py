#!/usr/bin/env python3
"""Frozen whole-share risk overlay for NFLX 0.4681."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent;SPEC=HERE/'nflx_04681_risk_overlay_preregistration_v1.json';LOCK=HERE/'nflx_04681_risk_overlay_preregistration_v1.lock.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def commission(shares):return max(1.0,.005*shares)
def load(p):
 with Path(p).open(newline='',encoding='utf-8-sig') as f:r=[x for x in csv.DictReader(f,delimiter=';') if x['Type']=='Buy']
 return [{'ticket':x['Ticket'],'open_date':x['Open time'][:10].replace('.','-'),'close_date':x['Close time'][:10].replace('.','-'),'open':float(x['Open price']),'close':float(x['Close price'])} for x in r]
def simulate(rows,capital,exposure):
 equity=capital;peak=capital;dd=0;pnls=[];skipped=0;year_pnl={}
 for r in rows:
  shares=math.floor(equity*exposure/(r['open']*1.001+commission(1)))
  if shares<1:skipped+=1;continue
  pnl=shares*(r['close']*(1-.001)-r['open']*(1+.001))-2*commission(shares)
  equity+=pnl;pnls.append(pnl);year_pnl[int(r['open_date'][:4])]=year_pnl.get(int(r['open_date'][:4]),0)+pnl;peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
 years=(datetime.fromisoformat(rows[-1]['close_date'])-datetime.fromisoformat(rows[0]['open_date'])).days/365.2425
 gains=sum(x for x in pnls if x>0);loss=-sum(x for x in pnls if x<0);cagr=(equity/capital)**(1/years)-1
 return {'exposure_fraction':exposure,'initial_capital_usd':capital,'final_equity_usd':equity,'net_pnl_usd':equity-capital,'return_pct':(equity/capital-1)*100,'cagr_pct':cagr*100,'maximum_drawdown_pct_close_to_close':dd*100,'profit_factor':gains/loss if loss else None,'executed_trades':len(pnls),'skipped_unaffordable':skipped,'regime_pnl_usd':{'2017-2020':sum(v for y,v in year_pnl.items() if y<=2020),'2021-2024':sum(v for y,v in year_pnl.items() if y>=2021)},'calmar':cagr/dd if dd else None}
def benchmark(rows,capital):
 first,last=rows[0],rows[-1];shares=math.floor((capital-commission(1))/(first['open']*1.001));cash=capital-shares*first['open']*1.001-commission(shares);final=cash+shares*last['close']*(1-.001)-commission(shares);years=(datetime.fromisoformat(last['close_date'])-datetime.fromisoformat(first['open_date'])).days/365.2425
 return {'shares':shares,'initial_price':first['open'],'final_price':last['close'],'final_equity_usd':final,'return_pct':(final/capital-1)*100,'cagr_pct':((final/capital)**(1/years)-1)*100}
def main():
 p=argparse.ArgumentParser();p.add_argument('--orders',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s=json.loads(SPEC.read_text());l=json.loads(LOCK.read_text())
 if sha(SPEC)!=l['preregistration_sha256'] or sha(a.orders)!=s['orders_sha256']:raise ValueError('frozen input mismatch')
 rows=load(a.orders);results=[simulate(rows,s['initial_capital_usd'],x) for x in s['exposure_fractions']]
 for r in results:r['passes_hard_gate']=r['maximum_drawdown_pct_close_to_close']<=20 and r['cagr_pct']>=12 and r['profit_factor']>=1.3 and all(x>0 for x in r['regime_pnl_usd'].values())
 passing=[r for r in results if r['passes_hard_gate']];selected=sorted(passing,key=lambda r:(-r['calmar'],r['exposure_fraction']))[0] if passing else None
 out={'schema_version':1,'decision':'PASS_RISK_OVERLAY' if selected else 'FAIL_RISK_OVERLAY','candidate':s['candidate'],'results':results,'selected_overlay':selected,'buy_and_hold_diagnostic':benchmark(rows,s['initial_capital_usd']),'selection_was_preregistered':True,'strategy_parameters_changed':False,'holdout_2025_accessed':False,'paper_authorized':False,'live_authorized':False}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
