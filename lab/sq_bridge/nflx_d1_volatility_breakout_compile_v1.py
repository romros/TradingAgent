#!/usr/bin/env python3
"""Compile the preregistered NFLX D1 breakout SQ discovery project."""
from __future__ import annotations
import csv,hashlib,json
from datetime import date,datetime,timezone
from pathlib import Path
from lab.sq_bridge.alquimia_project import build

ROOT=Path(__file__).resolve().parents[2]
SPEC=Path(__file__).with_name('nflx_d1_volatility_breakout_v1.json')
SCAFFOLD=Path('/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx')
SOURCE=ROOT/'data/ibkr_sq_v2/preflight/NFLXUSUSD_NYSE_RTH_D1_through_2024.csv'
REPORT=ROOT/'data/ibkr_sq_v2/preflight/nflx_through_2024_mechanical_preflight.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def epoch(value):return str(int(datetime.combine(date.fromisoformat(value),datetime.min.time(),tzinfo=timezone.utc).timestamp()*1000))
def prepare(target):
 rows=[]
 with SOURCE.open(newline='') as s:
  for r in csv.DictReader(s):
   if r['date']>'2024-12-31':raise ValueError('post-2024 row refused')
   rows.append(r)
 if not rows or rows[0]['date']!='2017-01-26' or rows[-1]['date']!='2024-12-31':raise ValueError('canonical date boundary mismatch')
 target.write_text(''.join(f"{r['date'].replace('-','.')},00:00,{float(r['open']):.6f},{float(r['high']):.6f},{float(r['low']):.6f},{float(r['close']):.6f},0\n" for r in rows))
 return {'rows':len(rows),'source_sha256':sha(SOURCE),'mt4_sha256':sha(target)}
def compile_campaign(output):
 spec=json.loads(SPEC.read_text());report=json.loads(REPORT.read_text())
 if spec['performance_accessed_for_this_family'] or report.get('decision')!='PASS_MECHANICAL_PREFLIGHT':raise ValueError('blind source preflight required')
 output.mkdir(parents=True,exist_ok=True);mt4=output/'NFLXUSUSD_NYSE_RTH_D1_2017_2024_MT4.csv';source=prepare(mt4);p=spec['periods'];d=spec['discovery']
 registry={'markets':{'NFLX':{'research_eligible':True,'sq_symbol':spec['sq_symbol'],'discovery_timeframe':'D1','discovery_slippage':0,'discovery_commission_per_order':0,'sq_resource_clone_from':'BTCUSD_ALQ_H4','sq_prune_resources':True,'sq_resource_remove_attributes':['cloneFrom','sourceTimezone'],'sq_resource_attributes':{'source':'1','barType':'1','precision':'D1','timezone':'America/New_York','dateFrom':epoch(p['train_from']),'dateTo':epoch(p['sealed_oos_to']),'uSymbol':'NFLX_IBKR_BREAKOUT_V1','uSymbolName':'NFLX_IBKR_BREAKOUT_V1','removeWeekends':'false','broker':'-1'},'sq_instrument_attributes':{'instrument':'NFLX_IBKR_BREAKOUT_V1','description':'NFLX D1 breakout research','tickSize':'0.001','tickStep':'0.001','minDistance':'0','tickValueInMoney':'0','dateFrom':'0','dateTo':'0','rows':'0','totalDays':'0','defaultSpread':'0','defaultSlippage':'0','decimals':'3','commissions':'','pointValue':'1','dataType':'1','recognizedFromOrders':'false','exchange':'NASDAQ','country':'US','sector':'Communication Services','swap':'','orderSizeMultiplier':'1','orderSizeStep':'1','broker':'-1'},'exit_at_end_of_day':False,'eod_exit_seconds':None,'signal_time_range_seconds':None,'exit_at_end_of_range':False,'maximum_trades_per_day':1,'venue_max_leverage':1}}}
 rp=output/'frozen_market_registry.json';rp.write_text(json.dumps(registry,indent=2,sort_keys=True)+'\n');method=json.loads((ROOT/'lab/sq_bridge/methodology_ibkr_sq_v1.json').read_text());method['methodology_id']=spec['campaign_id'];method['capital_usdc']=1000;method['small_account']['canonical_capital_usdc']=1000
 for key in ('hypothesis_screen','discovery'):
  if key in method:method[key]['minimum_trades_train']=d['minimum_train_trades'];method[key]['minimum_profit_factor_train']=d['minimum_profit_factor_train']
 mp=output/'frozen_methodology.json';mp.write_text(json.dumps(method,indent=2,sort_keys=True)+'\n');periods={'train_from':p['train_from'],'train_to':p['train_to'],'validation_from':p['validation_from'],'validation_to':p['validation_to'],'oos_from':p['sealed_oos_from'],'oos_to':p['sealed_oos_to'],'holdout_from':'2025-01-02','holdout_to':'2025-12-31'}
 cfx=output/'project.cfx';manifest=build(SCAFFOLD,cfx,'IBKR_NFLX_D1_VOLATILITY_BREAKOUT_V1','NFLX',rp,mp,date.fromisoformat(p['train_from']),date(2025,12,31),d['accepted_limit'],d['search_profile'],d['generation'],d['attempt_budget'],d['wall_time_budget_minutes'],None,d['direction'],periods_override=periods)
 result={'decision':'PASS_NFLX_BREAKOUT_DISCOVERY_READY','project_sha256':manifest['output_sha256'],'source':source,'preflight_sha256':sha(REPORT),'performance_accessed':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False};(output/'compile_receipt.json').write_text(json.dumps(result,indent=2)+'\n');return result
def main():print(json.dumps(compile_campaign(ROOT/'data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1'),indent=2))
if __name__=='__main__':main()
