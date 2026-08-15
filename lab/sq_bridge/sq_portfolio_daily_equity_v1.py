#!/usr/bin/env python3
"""Extract transparent metrics from SQ's Java dailyEquity block stream."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,struct,zipfile
from pathlib import Path

def decode(blob:bytes):
    if blob[:4]!=b'\xac\xed\x00\x05':raise ValueError('not a Java object stream')
    i=4;raw=b''
    while i<len(blob):
        token=blob[i];i+=1
        if token==0x7a:n=struct.unpack('>I',blob[i:i+4])[0];i+=4
        elif token==0x77:n=blob[i];i+=1
        elif token==0x78:continue
        else:raise ValueError(f'unsupported Java stream token {token:#x}')
        raw+=blob[i:i+n];i+=n
    count=struct.unpack('>I',raw[:4])[0]
    if len(raw)!=4+16*count:raise ValueError('unexpected dailyEquity payload size')
    return [(dt.datetime.fromtimestamp(struct.unpack('>q',raw[4+j*16:12+j*16])[0]/1000,dt.UTC).date(),struct.unpack('>d',raw[12+j*16:20+j*16])[0]) for j in range(count)]

def metrics(rows,start=dt.date(2022,1,1),capital=2000):
    rows=[(d,v) for d,v in rows if d>=start];peak=capital+rows[0][1];peak_date=rows[0][0];max_dd=0;dd_pair=None
    for d,pnl in rows:
        equity=capital+pnl
        if equity>peak:peak,peak_date=equity,d
        dd=(peak-equity)/peak*100
        if dd>max_dd:max_dd,dd_pair=dd,(peak_date,d)
    return {'first_date':str(rows[0][0]),'last_date':str(rows[-1][0]),'first_pnl':rows[0][1],'last_pnl':rows[-1][1],'return_pct_on_capital':rows[-1][1]/capital*100,'maximum_pnl':max(v for _,v in rows),'minimum_pnl':min(v for _,v in rows),'daily_equity_max_drawdown_pct':max_dd,'drawdown_peak_date':str(dd_pair[0]),'drawdown_trough_date':str(dd_pair[1]),'observations':len(rows)}

def extract(path:Path):
    with zipfile.ZipFile(path) as z:
        members={n:metrics(decode(z.read(n))) for n in z.namelist() if n.endswith('dailyEquity.bin')}
        parts=sorted(n.removeprefix('PortfolioParts/') for n in z.namelist() if n.startswith('PortfolioParts/') and n.endswith('.sqx'))
    return {'schema_version':1,'decision':'PASS_SQ_NATIVE_COMMON_WINDOW_PORTFOLIO_DIAGNOSTIC','sqx_path':str(path),'sqx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'period':'2022-01-01/2024-12-31','initial_capital':2000,'components':parts,'daily_equity':members,'limitations':['SQ Portfolio Master used one whole share per trade, not four fixed 25% sleeves.','SQ run used neutral costs; this is not IBKR net economics.','Daily equity ends 2024-12-30; EndTest closed balance is audited separately from exported orders.'],'paper_authorized':False,'live_authorized':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('sqx',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=extract(a.sqx);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
