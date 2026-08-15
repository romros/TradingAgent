#!/usr/bin/env python3
"""Frozen XOM monthly trend screen for a fifth independent portfolio edge."""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent;SPEC=HERE/'xom_monthly_tsmom_preregistration_v1.json';LOCK=HERE/'xom_monthly_tsmom_preregistration_v1.lock.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    rows=[]
    with path.open(newline='') as s:
        for r in csv.DictReader(s):
            if r['date']>'2024-12-31':raise ValueError('2025+ sealed')
            rows.append({'date':dt.date.fromisoformat(r['date']),**{k:float(r[k]) for k in ('open','close')}})
    return rows
def metrics(trades,capital):
    equity=peak=capital;dd=0;wins=losses=0.;monthly={}
    for t in trades:
        equity+=t['net'];peak=max(peak,equity);dd=max(dd,(peak-equity)/peak);monthly.setdefault(t['exit'][:7],0.);monthly[t['exit'][:7]]+=t['net']/capital
        if t['net']>0:wins+=t['net']
        else:losses-=t['net']
    values=list(monthly.values());sd=statistics.stdev(values) if len(values)>1 else 0;sharpe=statistics.mean(values)/sd*math.sqrt(12) if sd else None
    return {'trades':len(trades),'net_pnl':equity-capital,'net_return':equity/capital-1,'profit_factor':wins/losses if losses else None,'maximum_drawdown':dd,'annualized_monthly_sharpe':sharpe,'positive_years':len({t['exit'][:4] for t in trades if t['net']>0}),'position_changes':2*len(trades)}
def simulate(rows,lookback,start,end,cost):
    a,b=map(dt.date.fromisoformat,(start,end));months={}
    for i,r in enumerate(rows):months.setdefault((r['date'].year,r['date'].month),[]).append(i)
    reviews=sorted(v[-1] for v in months.values());position=None;trades=[]
    for i in reviews:
        if i<lookback or i+1>=len(rows):continue
        entry_i=i+1;day=rows[entry_i]['date']
        if day<a:continue
        desired=rows[i]['close']>rows[i-lookback]['close']
        if position is None and desired and day<=b:
            raw=rows[entry_i]['open'];price=raw*(1+cost['bps']/10000);shares=math.floor((500-cost['fee'])/price)
            if shares:position={'entry':day,'price':price,'shares':shares}
        elif position is not None and not desired:
            raw=rows[entry_i]['open'];price=raw*(1-cost['bps']/10000);net=position['shares']*(price-position['price'])-2*cost['fee'];trades.append({'entry':position['entry'].isoformat(),'exit':day.isoformat(),'shares':position['shares'],'net':net});position=None
        if day>b:break
    if position is not None:
        candidates=[r for r in rows if r['date']<=b];raw=candidates[-1]['close'];price=raw*(1-cost['bps']/10000);net=position['shares']*(price-position['price'])-2*cost['fee'];trades.append({'entry':position['entry'].isoformat(),'exit':candidates[-1]['date'].isoformat(),'shares':position['shares'],'net':net,'exit_type':'EndTest'})
    return trades
def run(source):
    spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
    if sha(SPEC)!=lock['preregistration_sha256'] or lock['performance_accessed_before_lock']:raise ValueError('lock mismatch')
    rows=load(source);costs={'tiered':{'fee':.35,'bps':2},'fixed':{'fee':1.,'bps':5},'stress':{'fee':1.,'bps':10}};results={}
    for v in spec['variants']:
        block={}
        for period,bounds in spec['periods'].items():block[period]={name:{'metrics':metrics(t:=simulate(rows,v['lookback_sessions'],*bounds,c),500),'trades':t} for name,c in costs.items()}
        results[v['id']]={'lookback_sessions':v['lookback_sessions'],'periods':block}
    g=spec['gates'];passes=[]
    for name in ('M6','M12'):
        val=results[name]['periods']['validation']['stress']['metrics'];oos=results[name]['periods']['oos']['stress']['metrics'];combined=results[name]['periods']['validation']['stress']['trades']+results[name]['periods']['oos']['stress']['trades'];cm=metrics(combined,500)
        passes.append(val['net_return']>0 and oos['net_return']>0 and (cm['profit_factor'] or 0)>=g['both_variants_combined_profit_factor_gte'] and cm['maximum_drawdown']<=g['both_variants_combined_maximum_drawdown_lte'])
        results[name]['combined_validation_oos_stress']=cm
    central=results['M12']['combined_validation_oos_stress'];passed=all(passes) and (central['annualized_monthly_sharpe'] or -99)>=g['central_M12_combined_annualized_sharpe_gte'] and central['position_changes']>=g['central_M12_completed_position_changes_gte']
    return {'schema_version':1,'decision':'PASS_STANDALONE_EDGE_PENDING_PORTFOLIO_CORRELATION' if passed else 'REJECT_FROZEN_XOM_TSMOM','preregistration_sha256':sha(SPEC),'source_sha256':sha(source),'results':results,'optimized':False,'post_2024_accessed':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=run(a.source);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
