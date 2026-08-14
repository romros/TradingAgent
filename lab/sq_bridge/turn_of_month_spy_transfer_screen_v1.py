#!/usr/bin/env python3
import argparse,datetime as dt,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load,trades,metrics
H=Path(__file__).resolve().parent;S=H/'turn_of_month_spy_transfer_preregistration_v1.json';L=H/'turn_of_month_spy_transfer_preregistration_v1.lock.json'
ap=argparse.ArgumentParser();ap.add_argument('--spy',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();spec=json.loads(S.read_text());lock=json.loads(L.read_text());digest=hashlib.sha256(S.read_bytes()).hexdigest()
if digest!=lock['preregistration_sha256']:raise ValueError('lock mismatch')
f=load(a.spy);pt={};r={'schema_version':1,'preregistration_sha256':digest,'optimized':False,'holdout_2025_accessed':False,'periods':{}}
for p,b in spec['periods'].items():
 if p=='holdout_2025':continue
 x=trades(f,*map(dt.date.fromisoformat,b));pt[p]=x;r['periods'][p]=metrics(x)
g=spec['gates'];v,o=metrics(pt['validation']),metrics(pt['oos_2024']);c=metrics(pt['validation']+pt['oos_2024'])
r['decision']={'pass':v['trades']>=g['validation_min_trades'] and o['trades']>=g['oos_min_trades'] and v['mean_return']>0 and o['mean_return']>0 and (v['profit_factor'] or 0)>=g['validation_and_oos_profit_factor_gte'] and (o['profit_factor'] or 0)>=g['validation_and_oos_profit_factor_gte'] and (c['monthly_sharpe'] or -999)>=g['combined_monthly_sharpe_gte'] and c['max_drawdown']<=g['combined_max_drawdown_lte'],'combined_validation_oos':c}
def inference(rows):
 vals=[x[1] for x in rows];mean=sum(vals)/len(vals);sd=(sum((x-mean)**2 for x in vals)/(len(vals)-1))**.5;t=mean/(sd/len(vals)**.5)
 try:
  from scipy.stats import t as student_t
  p=float(student_t.sf(t,len(vals)-1))
 except ImportError:p=.5*math.erfc(t/math.sqrt(2))
 return {'observations':len(vals),'mean_return':mean,'t_stat':t,'one_sided_p_value':p}
full=pt['train']+pt['validation']+pt['oos_2024'];r['statistical_evidence']={'full_2017_2024':inference(full),'validation_oos':inference(pt['validation']+pt['oos_2024'])}
r['cost_diagnostics']={}
for capital in (200,500,1000):
 commission_bps=2*.35/capital*10000
 for slippage_bps in (2,10):
  cost=(commission_bps+slippage_bps)/10000
  rows=[(d,x-cost) for d,x in pt['validation']+pt['oos_2024']]
  r['cost_diagnostics'][f'capital_{capital}_slippage_{slippage_bps}bps']={'roundtrip_cost_bps':commission_bps+slippage_bps,'metrics':metrics(rows)}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
