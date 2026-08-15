#!/usr/bin/env python3
"""Compare unique Portfolio Composer entries with four frozen Python rules."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from cat_0168_transfer_screen_v1 import frozen_orders
from cat_msft_jpm_portfolio_v1 import load_cat,load_jpm
from three_strategy_portfolio_v1 import load_msft,signals
from gold_tsmom_confirmation_screen_v1 import load as load_gold

PATTERN=re.compile(r"Order ACCEPTED '([^/]+)/.*?OpenTime=([0-9.]+) [^|]+\|OpenPrice=\$([0-9.]+)")
NAMES={'CAT_0168_FLOOR500':'CAT','MSFT_CAPITULATION_FLOOR500':'MSFT','JPM_MOMENTUM60_FLOOR500':'JPM','SGLN_TSMOM12_FLOOR500':'SGLN'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def sq_entries(path):
    with zipfile.ZipFile(path) as z:log=ET.fromstring(z.read('settings.xml')).find('.//PortfolioComposerLog').text
    lines=[line for line in log.splitlines() if 'Order ACCEPTED' in line];unique=list(dict.fromkeys(lines));out={v:[] for v in NAMES.values()}
    for line in unique:
        m=PATTERN.search(line)
        if not m or m.group(1) not in NAMES:raise ValueError(f'unrecognized accepted order: {line}')
        out[NAMES[m.group(1)]].append({'date':m.group(2).replace('.','-'),'price':float(m.group(3))})
    return out,len(lines)-len(unique)
def expected(cat_path,msft_path,jpm_path,gold_path):
    cat=[{'date':o['open_time'].date().isoformat(),'price':o['open_price']} for o in frozen_orders(load_cat(cat_path),'2022.01.01','2024.12.31')]
    msft=load_msft(msft_path);ms=[{'date':msft[i]['date'].isoformat(),'price':msft[i]['open']} for i in signals(msft) if dt.date(2022,1,1)<=msft[i]['date']<=dt.date(2024,12,31)]
    jpm=load_jpm(jpm_path);closes=[r['close'] for r in jpm];jp=[];last=-1
    for i in range(60,len(jpm)-21):
        if jpm[i]['date'].year>=2025:break
        if jpm[i]['date'].month==jpm[i+1]['date'].month or i+1<last or closes[i]<=closes[i-60]:continue
        entry=i+1;last=entry+20
        if dt.date(2022,1,1)<=jpm[entry]['date']<=dt.date(2024,12,31):jp.append({'date':jpm[entry]['date'].isoformat(),'price':jpm[entry]['open']})
    prices=load_gold(gold_path);months={}
    for day in sorted(prices):months.setdefault((day.year,day.month),[]).append(day)
    keys=sorted(months);gold=[];old=0
    for i in range(12,len(keys)-1):
        if keys[i+1][0]*12+keys[i+1][1]!=keys[i][0]*12+keys[i][1]+1:continue
        signal=months[keys[i]][-1];entry=months[keys[i+1]][0];position=int(prices[signal][1]>prices[months[keys[i-12]][-1]][1])
        if position>old and dt.date(2022,1,1)<=entry<=dt.date(2024,12,31):gold.append({'date':entry.isoformat(),'price':prices[entry][0]/100})
        old=position
    return {'CAT':cat,'MSFT':ms,'JPM':jp,'SGLN':gold}
def run(sqx,cat,msft,jpm,gold,tolerance=.0011):
    actual,duplicates=sq_entries(sqx);wanted=expected(cat,msft,jpm,gold);details={};passed=True
    for name in wanted:
        a=sorted(actual[name],key=lambda x:(x['date'],x['price']));w=sorted(wanted[name],key=lambda x:(x['date'],x['price']));pairs=[]
        for left,right in zip(a,w):pairs.append({'sq':left,'python':right,'date_exact':left['date']==right['date'],'price_abs_error':abs(left['price']-right['price'])})
        price_asserted=name!='MSFT'
        ok=len(a)==len(w) and all(p['date_exact'] and (not price_asserted or p['price_abs_error']<=tolerance) for p in pairs);passed&=ok
        details[name]={'sq_entries':len(a),'python_entries':len(w),'pass':ok,'price_parity_asserted':price_asserted,'price_scope_note':'MSFT Python candles are dividend-adjusted while SQ execution candles are split-consistent nominal OHLC.' if not price_asserted else None,'maximum_price_abs_error':max((p['price_abs_error'] for p in pairs),default=None),'mismatches':[p for p in pairs if not p['date_exact'] or (price_asserted and p['price_abs_error']>tolerance)]}
    return {'schema_version':1,'decision':'PASS_AGGREGATE_SIGNAL_PARITY_WITH_MSFT_PRICE_SCOPE_LIMIT' if passed else 'FAIL_AGGREGATE_ENTRY_PARITY','period':'2022-01-01/2024-12-31','duplicate_sq_log_lines_ignored':duplicates,'unique_sq_entries':sum(len(x) for x in actual.values()),'python_entries':sum(len(x) for x in wanted.values()),'price_tolerance':tolerance,'strategies':details,'inputs_sha256':{str(p):sha(p) for p in (sqx,cat,msft,jpm,gold)},'scope':'Entry dates for all four strategies; raw entry prices for CAT/JPM/SGLN. MSFT price parity is deliberately not asserted because its Python signal source is adjusted and SQ execution source is nominal. Individual exit parity remains governed by each strategy parity receipt.','paper_authorized':False,'live_authorized':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--sqx',type=Path,required=True);p.add_argument('--cat',type=Path,required=True);p.add_argument('--msft',type=Path,required=True);p.add_argument('--jpm',type=Path,required=True);p.add_argument('--gold',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=run(a.sqx,a.cat,a.msft,a.jpm,a.gold);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if r['decision'].startswith('PASS') else 1)
if __name__=='__main__':main()
