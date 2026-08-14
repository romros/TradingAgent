#!/usr/bin/env python3
"""Frozen cross-asset Donchian 55/20 staged screen."""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from datetime import date
from pathlib import Path

HERE=Path(__file__).resolve().parent
PREREG=HERE/'equity_donchian_preregistration_v1.json'
FROZEN_SHA256='e17f37d0dc1d4f6a5acb9a5b5fa732bbb3c43c64bde295dec2211cb0555159ac'

def load(path: Path, ceiling: date) -> list[dict]:
    if '2025' in path.name: raise ValueError('2025 sealed by filename')
    out=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            d=date.fromisoformat(r['date'])
            if d>=date(2025,1,1): raise ValueError('2025 sealed by row')
            if d<=ceiling: out.append({'date':d,'open':float(r['open']),'close':float(r['close'])})
    return out

def simulate(rows, start, end, capital=1000.0):
    equity=capital; peak=capital; dd=0.; pos=None; pending_exit=None; pending_entry=False; trades=[]
    closes=[]; last=None
    for r in rows:
        prior55=max(closes[-55:]) if len(closes)>=55 else None
        prior20=min(closes[-20:]) if len(closes)>=20 else None
        d=r['date']
        if start<=d<=end:
            last=r
            if pos and pending_exit:
                gross=pos['qty']*(r['open']-pos['price'])
                cost=pos['entry_cost']+1+0.001*pos['qty']*r['open']
                net=gross-cost; equity+=net
                trades.append({'entry':pos['date'].isoformat(),'exit':d.isoformat(),'net':net,'gross':gross,'costs':cost,'reason':pending_exit})
                pos=None; pending_exit=None
            if not pos and pending_entry:
                qty=math.floor(equity/r['open'])
                if qty: pos={'date':d,'price':r['open'],'qty':qty,'entry_cost':1+0.001*qty*r['open'],'held':0}
                pending_entry=False
            if pos:
                pos['held']+=1
                if prior20 is not None and r['close']<prior20: pending_exit='donchian_exit'
                elif pos['held']>=126: pending_exit='time'
                marked=equity+pos['qty']*(r['close']-pos['price'])-pos['entry_cost']-1-0.001*pos['qty']*r['close']
            else:
                if prior55 is not None and r['close']>prior55: pending_entry=True
                marked=equity
            peak=max(peak,marked); dd=max(dd,(peak-marked)/peak*100)
        closes.append(r['close'])
    if pos and last:
        gross=pos['qty']*(last['close']-pos['price'])
        cost=pos['entry_cost']+1+0.001*pos['qty']*last['close']; net=gross-cost; equity+=net
        trades.append({'entry':pos['date'].isoformat(),'exit':last['date'].isoformat(),'net':net,'gross':gross,'costs':cost,'reason':'segment_end'})
        pos=None
    wins=sum(t['net'] for t in trades if t['net']>0); losses=-sum(t['net'] for t in trades if t['net']<0)
    return {'closed_trades':len(trades),'net_pnl_usd':sum(t['net'] for t in trades),'return_pct':(equity/capital-1)*100,
            'profit_factor':wins/losses if losses else (1e9 if wins else 0.),'maximum_mark_to_market_drawdown_pct':dd,
            'open_trade_excluded':pos is not None,'trades':trades}

def aggregate(results):
    trades=[t for r in results.values() for t in r['trades']]
    wins=sum(t['net'] for t in trades if t['net']>0); losses=-sum(t['net'] for t in trades if t['net']<0)
    return {'pooled_closed_trades':len(trades),'pooled_profit_factor':wins/losses if losses else (1e9 if wins else 0.),
            'mean_sleeve_return_pct':sum(r['return_pct'] for r in results.values())/len(results),
            'positive_assets':sum(r['return_pct']>0 for r in results.values()),
            'maximum_single_asset_drawdown_pct':max(r['maximum_mark_to_market_drawdown_pct'] for r in results.values())}

def passes(a):
    return a['pooled_closed_trades']>=30 and a['pooled_profit_factor']>=1.15 and a['mean_sleeve_return_pct']>0 and a['positive_assets']>=5 and a['maximum_single_asset_drawdown_pct']<=30

def main():
    p=argparse.ArgumentParser();p.add_argument('--asset',action='append',required=True,metavar='NAME=CSV');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if FROZEN_SHA256=='TO_BE_FROZEN' or hashlib.sha256(PREREG.read_bytes()).hexdigest()!=FROZEN_SHA256: raise ValueError('preregistration hash mismatch')
    paths=dict(v.split('=',1) for v in a.asset)
    expected=json.loads(PREREG.read_text())['assets']
    if sorted(paths)!=sorted(expected): raise ValueError('exact frozen asset set required')
    pre={k:load(Path(v),date(2023,12,31)) for k,v in paths.items()}
    train={k:simulate(v,date(2018,1,1),date(2021,12,31)) for k,v in pre.items()}
    validation={k:simulate(v,date(2022,1,1),date(2023,12,31)) for k,v in pre.items()}; agg=aggregate(validation); ok=passes(agg)
    oos={'status':'SEALED'}
    if ok: oos={k:simulate(load(Path(v),date(2024,12,31)),date(2024,1,1),date(2024,12,31)) for k,v in paths.items()}
    report={'campaign_id':'ibkr-equity-d1-donchian-55-20-v1','preregistration_sha256':FROZEN_SHA256,'train':train,'validation':validation,
            'validation_aggregate':agg,'decision':'PASS_OPEN_OOS' if ok else 'REJECT_KEEP_OOS_SEALED','oos':oos}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'decision':report['decision'],'validation_aggregate':agg,'asset_returns':{k:v['return_pct'] for k,v in validation.items()},'oos':oos},indent=2))

if __name__=='__main__': main()
