#!/usr/bin/env python3
"""Compile the frozen XLF D1 price-action SQ discovery campaign."""
from __future__ import annotations
import csv,json,hashlib
from datetime import date,datetime,timezone
from pathlib import Path
from lab.sq_bridge.alquimia_project import build

ROOT=Path(__file__).resolve().parents[2]
SPEC=Path(__file__).with_suffix('.json')
SCAFFOLD=Path('/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx')
def epoch(value):return str(int(datetime.combine(date.fromisoformat(value),datetime.min.time(),tzinfo=timezone.utc).timestamp()*1000))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def prepare_source(source:Path,target:Path):
 target.parent.mkdir(parents=True,exist_ok=True);rows=[]
 with source.open(newline='') as stream:
  for r in csv.DictReader(stream):
   d=date.fromisoformat(r['date'])
   if date(2017,1,26)<=d<=date(2024,12,31):rows.append((d,r))
 target.write_text(''.join(f"{d:%Y.%m.%d},00:00,{float(r['open']):.6f},{float(r['high']):.6f},{float(r['low']):.6f},{float(r['close']):.6f},0\n" for d,r in rows))
 return {'rows':len(rows),'first':str(rows[0][0]),'last':str(rows[-1][0]),'source_sha256':sha(source),'mt4_sha256':sha(target)}
def compile_pilot(output_dir:Path):
 s=json.loads(SPEC.read_text());p=s['periods']
 if s['performance_accessed_before_freeze'] or s['promotion_allowed'] or s['volume_rules_allowed']:raise ValueError('campaign must remain blind, price-only and non-promotable')
 source=ROOT/s['adjusted_source'];mt4=output_dir/'XLF_ADJUSTED_D1_2017_2024_MT4.csv';source_info=prepare_source(source,mt4)
 output_dir.mkdir(parents=True,exist_ok=True)
 registry={'markets':{'XLF':{'research_eligible':True,'sq_symbol':s['sq_symbol'],'discovery_timeframe':'D1','discovery_slippage':0,'discovery_commission_per_order':0,'sq_resource_clone_from':'BTCUSD_ALQ_H4','sq_prune_resources':True,'sq_resource_remove_attributes':['cloneFrom','sourceTimezone'],'sq_resource_attributes':{'source':'1','barType':'1','precision':'D1','timezone':'America/New_York','dateFrom':epoch(p['train_from']),'dateTo':epoch(p['sealed_oos_to']),'uSymbol':'XLF_IBKR_V1','uSymbolName':'XLF_IBKR_V1','removeWeekends':'false','broker':'-1'},'sq_instrument_attributes':{'instrument':'XLF_IBKR_V1','description':'XLF adjusted D1 gross research','tickSize':'0.000001','tickStep':'0.000001','minDistance':'0','tickValueInMoney':'0','dateFrom':'0','dateTo':'0','rows':'0','totalDays':'0','defaultSpread':'0','defaultSlippage':'0','decimals':'6','commissions':'','pointValue':'1','dataType':'1','recognizedFromOrders':'false','exchange':'NYSEARCA','country':'US','sector':'Financials ETF','swap':'','orderSizeMultiplier':'1','orderSizeStep':'1','broker':'-1'},'exit_at_end_of_day':False,'eod_exit_seconds':None,'signal_time_range_seconds':None,'exit_at_end_of_range':False,'maximum_trades_per_day':1,'venue_max_leverage':1}}}
 rp=output_dir/'frozen_market_registry.json';rp.write_text(json.dumps(registry,indent=2,sort_keys=True)+'\n')
 method=json.loads((ROOT/'lab/sq_bridge/methodology_ibkr_sq_v1.json').read_text());method['methodology_id']=s['campaign_id'];method['capital_usdc']=1000;method['small_account']['canonical_capital_usdc']=1000
 for key in ('hypothesis_screen','discovery'):
  if key in method:method[key]['minimum_trades_train']=s['discovery']['minimum_train_trades'];method[key]['minimum_profit_factor_train']=s['discovery']['minimum_profit_factor_train']
 mp=output_dir/'frozen_methodology.json';mp.write_text(json.dumps(method,indent=2,sort_keys=True)+'\n')
 periods={'train_from':p['train_from'],'train_to':p['train_to'],'validation_from':p['validation_from'],'validation_to':p['validation_to'],'oos_from':p['sealed_oos_from'],'oos_to':p['sealed_oos_to'],'holdout_from':'2025-01-02','holdout_to':'2025-12-31'}
 cfx=output_dir/'project.cfx';d=s['discovery'];m=build(SCAFFOLD,cfx,'IBKR_XLF_D1_PRICE_ACTION_V1','XLF',rp,mp,date.fromisoformat(p['train_from']),date(2025,12,31),d['accepted_limit'],d['search_profile'],d['generation'],d['attempt_budget'],d['wall_time_budget_minutes'],None,d['direction'],periods_override=periods)
 r={'decision':'PASS_THEORETICAL_DISCOVERY_READY','project':str(cfx),'manifest':str(cfx.with_suffix('.manifest.json')),'project_sha256':m['output_sha256'],'source':source_info,'source_performance_accessed':False,'sqcli_started':False,'promotion_allowed':False,'paper_authorized':False,'live_authorized':False};(output_dir/'compile_receipt.json').write_text(json.dumps(r,indent=2)+'\n');return r
if __name__=='__main__':print(json.dumps(compile_pilot(ROOT/'data/ibkr_sq_v2/xlf_d1_price_action_pilot'),indent=2))
