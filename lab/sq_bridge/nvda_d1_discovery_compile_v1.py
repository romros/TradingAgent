#!/usr/bin/env python3
"""Compile the blind NVDA D1 discovery project and frozen MT4 source."""
from __future__ import annotations
import csv, hashlib, json
from datetime import date, datetime, timezone
from pathlib import Path
from lab.sq_bridge.alquimia_project import build

ROOT=Path(__file__).resolve().parents[2]; SPEC=Path(__file__).with_name('nvda_d1_discovery_v1.json')
SOURCE=ROOT/'data/ibkr_sq_v2/tech_momentum60_transfer_v1/adjusted/NVDA_ADJUSTED_D1_2017_2024.csv'
SCAFFOLD=Path('/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def epoch(v): return str(int(datetime.combine(date.fromisoformat(v),datetime.min.time(),tzinfo=timezone.utc).timestamp()*1000))
def compile_campaign(out):
 s=json.loads(SPEC.read_text()); raw=list(csv.DictReader(SOURCE.open(newline='')))
 if sha(SOURCE)!='0d58c90579652e1568cdd40486acf2ca8c64a3b4660f7e735dd5d420e67cd0ed' or raw[0]['date']!='2017-01-03' or raw[-1]['date']!='2024-12-31': raise ValueError('frozen NVDA source mismatch')
 if any(r['date']>'2024-12-31' for r in raw): raise ValueError('post-2024 row refused')
 out.mkdir(parents=True,exist_ok=True); mt4=out/'NVDA_ADJUSTED_D1_2017_2024_MT4.csv'
 with mt4.open('w',newline='') as f:
  w=csv.writer(f)
  for r in raw:w.writerow([r['date'].replace('-','.'),'00:00',r['open'],r['high'],r['low'],r['close'],0])
 p=s['periods'];d=s['discovery'];market={'research_eligible':True,'sq_symbol':s['sq_symbol'],'discovery_timeframe':'D1','discovery_slippage':0,'discovery_commission_per_order':0,'sq_resource_clone_from':'BTCUSD_ALQ_H4','sq_prune_resources':True,'sq_resource_remove_attributes':['cloneFrom','sourceTimezone'],'sq_resource_attributes':{'source':'1','barType':'1','precision':'D1','timezone':'America/New_York','dateFrom':epoch(p['train_from']),'dateTo':epoch(p['sealed_oos_to']),'uSymbol':'NVDA_IBKR_D1_V1','uSymbolName':'NVDA_IBKR_D1_V1','removeWeekends':'false','broker':'-1'},'sq_instrument_attributes':{'instrument':'NVDA_IBKR_D1_V1','description':'NVDA adjusted D1 research','tickSize':'0.000001','tickStep':'0.000001','minDistance':'0','tickValueInMoney':'0','dateFrom':'0','dateTo':'0','rows':'0','totalDays':'0','defaultSpread':'0','defaultSlippage':'0','decimals':'6','commissions':'','pointValue':'1','dataType':'1','recognizedFromOrders':'false','exchange':'NASDAQ','country':'US','sector':'Technology','swap':'','orderSizeMultiplier':'1','orderSizeStep':'1','broker':'-1'},'exit_at_end_of_day':False,'eod_exit_seconds':None,'signal_time_range_seconds':None,'exit_at_end_of_range':False,'maximum_trades_per_day':1,'venue_max_leverage':1}
 registry={'markets':{'NVDA':market}};rp=out/'frozen_market_registry.json';rp.write_text(json.dumps(registry,indent=2,sort_keys=True)+'\n')
 method=json.loads((ROOT/'lab/sq_bridge/methodology_ibkr_sq_v1.json').read_text());method['methodology_id']=s['campaign_id'];method['capital_usdc']=1000;method['small_account']['canonical_capital_usdc']=1000
 for key in ('hypothesis_screen','discovery'):
  if key in method:method[key]['minimum_trades_train']=d['minimum_train_trades'];method[key]['minimum_profit_factor_train']=d['minimum_profit_factor_train']
 mp=out/'frozen_methodology.json';mp.write_text(json.dumps(method,indent=2,sort_keys=True)+'\n')
 periods={'train_from':p['train_from'],'train_to':p['train_to'],'validation_from':p['validation_from'],'validation_to':p['validation_to'],'oos_from':p['sealed_oos_from'],'oos_to':p['sealed_oos_to'],'holdout_from':'2025-01-02','holdout_to':'2025-12-31'}
 manifest=build(SCAFFOLD,out/'project.cfx','IBKR_NVDA_D1_SIMPLE_DISCOVERY_V1','NVDA',rp,mp,date.fromisoformat(p['train_from']),date(2025,12,31),d['accepted_limit'],d['search_profile'],d['generation'],d['attempt_budget'],d['wall_time_budget_minutes'],None,d['direction'],periods_override=periods)
 result={'decision':'PASS_NVDA_D1_DISCOVERY_READY','source_sha256':sha(SOURCE),'mt4_sha256':sha(mt4),'rows':len(raw),'project_sha256':manifest['output_sha256'],'performance_accessed':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False};(out/'compile_receipt.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':print(json.dumps(compile_campaign(ROOT/'data/ibkr_sq_v2/nvda_d1_simple_discovery_v1'),indent=2))
