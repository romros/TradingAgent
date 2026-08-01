"""4H EURUSD/XAUUSD campaign from BrokerageService M1 parquet."""
from __future__ import annotations
import glob, itertools, json
from pathlib import Path
import numpy as np
import pandas as pd

DATA_ROOT=Path('/datafiles/historical_parquet')
OUT=Path('/work/lab/out/intraday_fx_campaign')
OUT.mkdir(parents=True,exist_ok=True)
SYMBOLS=('EURUSD','XAUUSD')
DEV_END='2013-12-31'; VAL_END='2019-12-31'
LEVERAGES=(1,1.5,2,3,4,5,7.5,10)
CAPITAL=250.; COL_PCT=.20; COL_PCTS=(.05,.10,.15,.20); GAS_RT=.22; FINANCING=.06
VARIABLE_COST={'EURUSD':.0002,'XAUUSD':.0008}

def load_4h(symbol):
    files=glob.glob(str(DATA_ROOT/symbol/'tf=1m/year=*/month=*/data.parquet'))
    parts=[]
    for p in files:
        d=pd.read_parquet(p,columns=['ts','open','high','low','close','volume'])
        parts.append(d)
    d=pd.concat(parts,ignore_index=True).drop_duplicates('ts').sort_values('ts')
    d.index=pd.to_datetime(d.pop('ts'),unit='s',utc=True)
    agg=d.resample('4h',origin='epoch').agg(O=('open','first'),H=('high','max'),
        L=('low','min'),C=('close','last'),V=('volume','sum'),count=('close','count'))
    agg=agg.dropna()
    # Require at least one hour of real minutes and non-flat bar.
    return agg[(agg['count']>=60)&(agg.H>agg.L)].loc['2004-01-01':]

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(s,n):
    x=s.diff(); g=x.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    l=(-x.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+g/l.replace(0,np.nan))
def atr(d,n=14):
    tr=pd.concat([d.H-d.L,(d.H-d.C.shift()).abs(),(d.L-d.C.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def signals(family,d,p):
    c,o=d.C,d.O; out=pd.Series(0,index=d.index,dtype=int)
    if family=='bb_reversion':
        period,z,threshold=p; m=c.rolling(period).mean(); sd=c.rolling(period).std(ddof=0)
        out[(c<m-z*sd)&(rsi(c,7)<threshold)]=1
    elif family=='donchian_breakout':
        n,trend_n=p; out[(c>d.H.rolling(n).max().shift(1))&(c>ema(c,trend_n))]=1
        out[(c<d.L.rolling(n).min().shift(1))&(c<ema(c,trend_n))]=-1
    elif family=='trend_pullback':
        fast,slow,threshold=p; rr=rsi(c,7); f=ema(c,fast); s=ema(c,slow)
        out[(f>s)&(c<f)&(rr<threshold)]=1
        out[(f<s)&(c>f)&(rr>100-threshold)]=-1
    elif family=='vol_expansion':
        mult,look=p; a=atr(d); body=(c-o).abs()
        out[(body>mult*a)&(c>o)&(c>c.shift(look))]=1
        out[(body>mult*a)&(c<o)&(c<c.shift(look))]=-1
    elif family=='large_body_reversal':
        mult,trend_n=p; a=atr(d); body=(c-o)/o; trend=c/ema(c,trend_n)-1
        out[(body < -mult*a/c)&(trend>0)]=1
        out[(body > mult*a/c)&(trend<0)]=-1
    elif family=='ma_trend':
        fast,slow=p; f=ema(c,fast); s=ema(c,slow)
        out[(f>s)&(f.shift(1)<=s.shift(1))]=1
        out[(f<s)&(f.shift(1)>=s.shift(1))]=-1
    return out

GRIDS={
 'bb_reversion':[(20,z,t) for z in (1.5,2,2.5) for t in (20,30,40)],
 'donchian_breakout':[(n,t) for n in (20,40,80) for t in (50,100)],
 'trend_pullback':[(f,s,t) for f in (10,20) for s in (50,100) for t in (25,35)],
 'vol_expansion':[(m,l) for m in (1,1.5,2) for l in (3,6,12)],
 'large_body_reversal':[(m,t) for m in (1,1.5,2) for t in (50,100)],
 'ma_trend':[(f,s) for f in (10,20,40) for s in (50,100,200) if f<s],
}
HOLDS=(1,2,3,6)

def make_trades(d,sig,hold):
    rows=[]; last_exit=-1
    for i in np.flatnonzero(sig.values):
        entry=i+1; exit_=entry+hold
        if entry<=last_exit or exit_>=len(d): continue
        side=int(sig.iloc[i]); ep=float(d.O.iloc[entry]); xp=float(d.O.iloc[exit_])
        window=d.iloc[entry:exit_+1]
        move=side*(xp-ep)/ep
        mae=(ep-window.L.min())/ep if side==1 else (window.H.max()-ep)/ep
        rows.append({'signal':str(d.index[i]),'entry':str(d.index[entry]),'exit':str(d.index[exit_]),
                     'year':d.index[entry].year,'side':side,'move':move,'mae':float(mae),'bars':hold})
        last_exit=exit_
    return pd.DataFrame(rows)

def simulate(trades,symbol,lev=1,cost_mult=1,col_pct=COL_PCT):
    cap=CAPITAL; peak=cap; maxdd=0; pnls=[]; liq=0; dates=[]
    for row in trades.itertuples():
        col=cap*col_pct; nominal=col*lev
        if row.mae>=1/lev:
            pnl=-col-GAS_RT*cost_mult; liq+=1
        else:
            variable=nominal*VARIABLE_COST[symbol]*cost_mult
            borrowed=nominal*max(1-1/lev,0)
            finance=borrowed*FINANCING*(row.bars*4/24/365)
            pnl=nominal*row.move-variable-GAS_RT*cost_mult-finance
        cap=max(cap+pnl,0); peak=max(peak,cap); maxdd=max(maxdd,(peak-cap)/peak if peak else 1)
        pnls.append(pnl); dates.append(pd.Timestamp(row.entry))
        if cap<=0: break
    p=np.array(pnls); wins=p[p>0].sum(); losses=-p[p<0].sum()
    ser=pd.Series(p,index=pd.DatetimeIndex(dates)) if len(p) else pd.Series(dtype=float)
    monthly=ser.resample('ME').sum() if len(ser) else ser
    yearly=ser.resample('YE').sum() if len(ser) else ser
    return {'n':len(p),'pf':float(wins/losses) if losses else 99.,'ev':float(p.mean()) if len(p) else -99,
            'capital_final':float(cap),'max_dd':float(maxdd),'liq_rate':liq/max(len(p),1),
            'monthly_p5':float(monthly.quantile(.05)) if len(monthly) else -99,
            'positive_years':float((yearly>0).mean()) if len(yearly) else 0}

def split(t,name):
    x=pd.to_datetime(t.entry,utc=True)
    if name=='dev': return t[x<=DEV_END]
    if name=='validation': return t[(x>'2013-12-31')&(x<=VAL_END)]
    return t[x>'2019-12-31']

def select(data):
    chosen=[]
    for family,grid in GRIDS.items():
        variants=[]
        for symbol,p,hold in itertools.product(SYMBOLS,grid,HOLDS):
            t=make_trades(data[symbol],signals(family,data[symbol],p),hold)
            devtr=split(t,'dev'); feasible=[]
            for lev,col_pct in itertools.product(LEVERAGES,COL_PCTS):
                sim=simulate(devtr,symbol,lev,1,col_pct); stress=simulate(devtr,symbol,lev,2,col_pct)
                if (sim['n']>=50 and sim['ev']>0 and stress['ev']>0 and sim['max_dd']<=.20
                        and sim['liq_rate']<=.01):
                    # Sample size is a gate, not an unbounded reward. Rank by
                    # quality under normal and stressed costs, penalising DD.
                    score=(np.log(max(sim['pf'],.01))
                           +np.log(max(stress['pf'],.01))-2*sim['max_dd'])
                    feasible.append((score,lev,col_pct,sim))
            if feasible:
                score,dev_lev,dev_col,dev=max(feasible,key=lambda x:x[0])
            else:
                score,dev_lev,dev_col,dev=-99,None,None,simulate(devtr,symbol)
            variants.append((score,symbol,p,hold,t,dev,dev_lev,dev_col))
        best=max(variants,key=lambda x:x[0]); _,symbol,p,hold,t,dev,dev_lev,dev_col=best
        val=simulate(split(t,'validation'),symbol); test=simulate(split(t,'test'),symbol)
        same=[v for v in variants if v[1]==symbol]
        robust=np.mean([simulate(split(v[4],'validation'),symbol,v[6] or 1,1,v[7] or COL_PCT)['ev']>0 for v in same])
        chosen.append({'family':family,'symbol':symbol,'params':p,'hold':hold,'trades':t,
                       'dev':dev,'dev_leverage':dev_lev,'dev_collateral_pct':dev_col,'validation':val,'test':test,'robust':float(robust)})
    return chosen

def leverage_gate(item):
    rows=[]; chosen=None
    valtr=split(item['trades'],'validation'); testtr=split(item['trades'],'test')
    for lev,col_pct in itertools.product(LEVERAGES,COL_PCTS):
        val=simulate(valtr,item['symbol'],lev,1,col_pct); sv=simulate(valtr,item['symbol'],lev,2,col_pct)
        test=simulate(testtr,item['symbol'],lev,1,col_pct); st=simulate(testtr,item['symbol'],lev,2,col_pct)
        select_ok=(val['pf']>=1.2 and val['max_dd']<=.20 and val['liq_rate']<=.01 and
                   val['monthly_p5']>=-25 and sv['ev']>0)
        test_ok=(test['pf']>=1.2 and test['max_dd']<=.25 and test['liq_rate']==0 and
                 test['monthly_p5']>=-25 and st['ev']>0)
        rows.append({'leverage':lev,'collateral_pct':col_pct,'selection_pass':select_ok,'test_pass':test_ok,
                     'validation':val,'stress_validation':sv,'test':test,'stress_test':st})
        if select_ok: chosen=(lev,col_pct)
    return chosen,rows

def main():
    data={s:load_4h(s) for s in SYMBOLS}; results=[]
    coverage={s:{'bars':len(d),'start':str(d.index.min()),'end':str(d.index.max())} for s,d in data.items()}
    for item in select(data):
        config,sweep=leverage_gate(item); lev,col_pct=config if config else (None,None)
        row=next((x for x in sweep if x['leverage']==lev and x['collateral_pct']==col_pct),None)
        samples={k:len(split(item['trades'],k)) for k in ('dev','validation','test')}
        accepted=(samples['validation']>=25 and samples['test']>=25 and len(item['trades'])>=100 and
                  row is not None and row['validation']['pf']>=1.25 and row['test']['pf']>=1.25 and item['robust']>=.70 and
                  lev is not None and row['test_pass'])
        results.append({k:v for k,v in item.items() if k!='trades'}|{'samples':samples,
            'selected_leverage':lev,'selected_collateral_pct':col_pct,
            'selected_validation':row['validation'] if row else None,'selected_test':row['test'] if row else None,
            'leverage_sweep':sweep,'accepted':accepted})
    artifact={'splits':{'dev_end':DEV_END,'validation_end':VAL_END},'coverage':coverage,'results':results}
    (OUT/'results.json').write_text(json.dumps(artifact,indent=2,default=str))
    lines=['# Intraday FX campaign','', '| Family | Symbol | Params | Hold | N val/test | PF val | PF test | Lev/Col | Gate |',
           '|---|---|---|---:|---:|---:|---:|---:|---|']
    for r in results:
        if r['dev_leverage'] is None:
            lines.append(f"| {r['family']} | - | - | - | - | - | - | - | NO_FEASIBLE_DEV |")
        else:
            lines.append(f"| {r['family']} | {r['symbol']} | `{r['params']}` | {r['hold']} | {r['samples']['validation']}/{r['samples']['test']} | {(r['selected_validation'] or r['validation'])['pf']:.2f} | {(r['selected_test'] or r['test'])['pf']:.2f} | {(str(r['selected_leverage'])+'x/'+str(int(100*r['selected_collateral_pct']))+'%') if r['selected_leverage'] else '-'} | {'ACCEPTED' if r['accepted'] else 'REJECTED'} |")
    (OUT/'SUMMARY.md').write_text('\n'.join(lines)+'\n'); print('\n'.join(lines)); print(coverage)

if __name__=='__main__': main()
