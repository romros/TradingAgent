#!/usr/bin/env python3
"""Trade-by-trade parity for exact-month SGLN TSMOM12 SQ versus Python."""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json
from pathlib import Path
from gold_tsmom_confirmation_screen_v1 import load,monthly
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def expected(path):
 prices=load(path); rows=monthly(prices,0); lo,hi=dt.date(2019,1,1),dt.date(2024,12,31);changes=[];old=0
 for day,_,pos,_ in rows:
  if lo<=day<=hi and pos!=old:changes.append((day,pos,prices[day][0]/100))
  if day>=lo:old=pos
 out=[];opened=None
 for day,pos,open_ in changes:
  if pos==1:opened=(day,open_)
  elif opened:out.append({'open_date':opened[0],'open_price':opened[1],'close_date':day,'close_price':open_,'close_type':'Exit Signal'});opened=None
 if opened:
  end=max(day for day in prices if day<=hi);out.append({'open_date':opened[0],'open_price':opened[1],'close_date':end,'close_price':prices[end][1]/100,'close_type':'EndTest'})
 return out
def observed(path):
 out=[]
 with Path(path).open(newline='',encoding='utf-8-sig') as f:
  for row in csv.DictReader(f,delimiter=';'):
   def val(key):return row[key].strip('"')
   out.append({'open_date':dt.datetime.strptime(val('Open time'),'%Y.%m.%d %H:%M:%S').date(),'open_price':float(val('Open price').replace(',','.')),'close_date':dt.datetime.strptime(val('Close time'),'%Y.%m.%d %H:%M:%S').date(),'close_price':float(val('Close price').replace(',','.')),'close_type':val('Close type')})
 return out
def run(source,orders):
 a,b=expected(source),observed(orders);pairs=[]
 for left,right in zip(a,b):
  pairs.append({'python':{**left,'open_date':left['open_date'].isoformat(),'close_date':left['close_date'].isoformat()},'sq':{**right,'open_date':right['open_date'].isoformat(),'close_date':right['close_date'].isoformat()},'dates_exact':left['open_date']==right['open_date'] and left['close_date']==right['close_date'],'types_exact':left['close_type']==right['close_type'],'max_price_abs_error_gbp':max(abs(left['open_price']-right['open_price']),abs(left['close_price']-right['close_price']))})
 passed=len(a)==len(b) and all(x['dates_exact'] and x['types_exact'] and x['max_price_abs_error_gbp']<=0.000051 for x in pairs)
 return {'schema_version':1,'decision':'PASS_EXACT_SIGNAL_AND_TRADE_PARITY' if passed else 'REJECT_PARITY','strategy':'SGLN_TSMOM12_MONTHLY_NATIVE_V1','python_trades':len(a),'sq_trades':len(b),'pairs':pairs,'maximum_price_abs_error_gbp':max((x['max_price_abs_error_gbp'] for x in pairs),default=None),'source_sha256':sha(source),'orders_sha256':sha(orders),'sizing_and_cost_parity':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--orders',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=run(a.source,a.orders);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if r['decision'].startswith('PASS') else 1)
if __name__=='__main__':main()
