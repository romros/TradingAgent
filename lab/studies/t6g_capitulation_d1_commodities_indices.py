"""
T6g — Commodities + índexs addicionals per capitulation_d1

Actius: GLD (Gold), SPY (S&P500), ^GDAXI (DAX)
Setup: capitulation_d1 (body < -2% + close < BB_lower(20,2)) — sense canvis
Gate: D1 per asset (T6e)

Executar: python3 lab/studies/t6g_capitulation_d1_commodities_indices.py
"""
from __future__ import annotations
import sys, csv, json, warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / 'lab' / 'out'
OUT_DIR.mkdir(exist_ok=True)

FEE = 5.38; CAPITAL = 250.0; COL_PCT = 0.20; COL_MAX = 60.0; COL_MIN = 15.0; LEV = 20
YEARS_BACK = 13

GATE_D1 = dict(N_min=35, WR_min=60.0, EV_min=8.0, PF_min=1.8,
               liq_max=5.0, WF_min=70.0, MC_min=90.0, MAE_max=1.5)

ASSETS = [
    ('GLD',    'Gold ETF (XAU proxy)'),
    ('SPY',    'S&P 500 ETF'),
    ('^GDAXI', 'DAX (Alemanya)'),
]

def download_d1(ticker):
    import yfinance as yf
    end = datetime.now(timezone.utc)
    start = end.replace(year=end.year - YEARS_BACK)
    df = yf.download(ticker, start=start.strftime('%Y-%m-%d'),
                     end=end.strftime('%Y-%m-%d'), interval='1d',
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[['Open','High','Low','Close']].copy()
    df.columns = ['O','H','L','C']
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.dropna()

def gen_signal(df, body_thresh=-0.02):
    C,O,H,L = df['C'].values,df['O'].values,df['H'].values,df['L'].values
    N = len(C)
    bb_lo = np.full(N, np.nan)
    for i in range(19, N):
        w = C[i-19:i+1]; bb_lo[i] = w.mean() - 2*w.std(ddof=0)
    body = (C - O) / np.maximum(O, 1e-9)
    out = []
    for i in range(50, N-1):
        if body[i] >= body_thresh: continue
        if np.isnan(bb_lo[i]) or C[i] >= bb_lo[i]: continue
        o1,h1,l1,c1 = O[i+1],H[i+1],L[i+1],C[i+1]
        out.append({'ts': df.index[i+1], 'yr': df.index[i+1].year,
                    'move': (c1-o1)/o1, 'mae': (o1-l1)/o1, 'mfe': (h1-o1)/o1})
    return out

def validate(ticker, trades):
    if not trades:
        return {'ticker': ticker, 'n': 0, 'status': 'REJECTED', 'reason': 'no_trades'}
    moves = np.array([t['move'] for t in trades])
    maes  = np.array([t['mae']  for t in trades])
    mfes  = np.array([t['mfe']  for t in trades])
    years = np.array([t['yr']   for t in trades])
    N = len(moves)
    pnl_base = 4000.0 * moves
    wr_base  = 100*np.mean(pnl_base > 0)
    w,l = pnl_base[pnl_base>0], pnl_base[pnl_base<=0]
    pf_base = abs(w.sum()/l.sum()) if len(l)>0 and l.sum()!=0 else 99.0
    liq_th = 1.0/LEV; cap = CAPITAL; dp = []
    for i in range(N):
        col = min(max(cap*COL_PCT, COL_MIN), COL_MAX)
        if cap < COL_MIN: break
        pnl = (-col-FEE) if maes[i]>=liq_th else (col*LEV*moves[i]-FEE)
        dp.append(pnl); cap = max(0, cap+pnl)
    dp = np.array(dp)
    liq_rate = 100*np.mean(maes>=liq_th)
    wr_dep = 100*np.mean(dp>0) if len(dp)>0 else 0
    wd,ld = dp[dp>0], dp[dp<=0]
    pf_dep = abs(wd.sum()/ld.sum()) if len(ld)>0 and ld.sum()!=0 else 99.0
    ev_dep = float(np.mean(dp)) if len(dp)>0 else 0.0
    cap_final = float(cap)
    eq = [CAPITAL]
    for p in dp: eq.append(eq[-1]+p)
    peak = eq[0]; mdd = 0.0
    for e in eq:
        if e>peak: peak=e
        dd=(peak-e)/peak if peak>0 else 0; mdd=max(mdd,dd)
    mae_med = round(100*float(np.median(maes)),2)
    mfe_med = round(100*float(np.median(mfes)),2)
    mc = round(100*sum(1 for _ in range(2000) if np.sum(np.random.permutation(moves))>0)/2000, 1)
    unique_yrs = sorted(set(years)); wf_pos = 0; yearly = {}
    for yr in unique_yrs:
        mask = years==yr; yr_pnl = pnl_base[mask]
        if len(yr_pnl)==0: continue
        total = float(yr_pnl.sum())
        yearly[yr] = {'n': int(mask.sum()), 'wr': round(100*float(np.mean(yr_pnl>0)),1), 'total': round(total,1)}
        if total>0: wf_pos+=1
    wf_str = f'{wf_pos}/{len(unique_yrs)}'
    wf_pct = 100*wf_pos/max(len(unique_yrs),1)
    span = max(unique_yrs)-min(unique_yrs)+1 if len(unique_yrs)>1 else 1
    tpy = round(N/span, 1)
    g = GATE_D1
    criteria = {'N': N>=g['N_min'], 'WR': wr_base>=g['WR_min'], 'EV': ev_dep>=g['EV_min'],
                'PF': pf_dep>=g['PF_min'], 'liq': liq_rate<=g['liq_max'],
                'WF': wf_pct>=g['WF_min'], 'MC': mc>=g['MC_min'], 'MAE': mae_med<=g['MAE_max']}
    n_pass = sum(criteria.values())
    if N<20 or mc<90 or wf_pct<60 or ev_dep<=0:
        status = 'REJECTED'
        if N<20: reason = f'N={N} < 20'
        elif mc<90: reason = f'MC {mc}% < 90%'
        elif wf_pct<60: reason = f'WF {wf_pct:.0f}% < 60%'
        else: reason = f'EV {ev_dep:.1f}$ ≤ 0'
    elif n_pass==8:
        status = 'ACCEPTED_D1_ASSET'; reason = 'Passes all 8 D1 gate criteria'
    elif n_pass>=5 and criteria['MC'] and criteria['WF']:
        fails = [k for k,v in criteria.items() if not v]
        status = 'WATCHLIST'; reason = f'{n_pass}/8. Fails: {", ".join(fails)}'
    else:
        fails = [k for k,v in criteria.items() if not v]
        status = 'REJECTED'; reason = f'{n_pass}/8, fails: {", ".join(fails)}'
    return {'ticker': ticker, 'n': N, 'tpy': tpy,
            'wr_base': round(wr_base,1), 'pf_base': round(pf_base,2),
            'ev_dep': round(ev_dep,2), 'pf_dep': round(pf_dep,2),
            'liq_pct': round(liq_rate,1), 'cap_final': round(cap_final,0),
            'mdd_pct': round(100*mdd,1), 'mae_med': mae_med, 'mfe_med': mfe_med,
            'mc': mc, 'wf': wf_str, 'wf_pct': round(wf_pct,1),
            'criteria': criteria, 'criteria_pass': n_pass,
            'yearly': yearly, 'status': status, 'reason': reason}

print(f'\n{"="*90}')
print('T6g — COMMODITIES + ÍNDEXS: capitulation_d1')
print(f'{"="*90}\n')

results = {}
for ticker, desc in ASSETS:
    print(f'  [{ticker}] {desc} — descarregant... ', end='', flush=True)
    try:
        df = download_d1(ticker)
        n_yrs = (df.index[-1]-df.index[0]).days/365.25
        print(f'{len(df)} candles ({n_yrs:.1f}a)')
        trades = gen_signal(df)
        r = validate(ticker, trades)
        results[ticker] = r
    except Exception as e:
        print(f'ERROR: {e}'); continue

print()
for ticker, r in results.items():
    cr = r.get('criteria', {}); flags = {k:'✓' if v else '✗' for k,v in cr.items()} if cr else {}
    desc = dict(ASSETS).get(ticker, ticker)
    print(f'  ── {ticker} ({desc}) ──')
    print(f'    N={r["n"]} ({r["tpy"]}t/any)  WR_base={r["wr_base"]}%  PF_base={r["pf_base"]}')
    print(f'    Deploy 20x: EV={r["ev_dep"]:+.1f}$  PF={r["pf_dep"]}  liq={r["liq_pct"]}%  cap={r["cap_final"]}$  MaxDD={r["mdd_pct"]}%')
    print(f'    MAE med={r["mae_med"]}%  MFE med={r["mfe_med"]}%')
    print(f'    MC={r["mc"]}%  WF={r["wf"]} ({r["wf_pct"]}%)')
    if flags:
        gl = '  '.join(f'{k}:{flags[k]}' for k in ['N','WR','EV','PF','liq','WF','MC','MAE'])
        print(f'    Gate: {gl}  ({r["criteria_pass"]}/8)')
    print(f'    → {r["status"]} — {r["reason"]}')
    if r.get('yearly'):
        recent = {yr:yd for yr,yd in sorted(r['yearly'].items()) if yr>=2020}
        if recent:
            row = '  '.join(f"{yr}:{yd['n']}t/{yd['wr']:.0f}%/{yd['total']:+.0f}$" for yr,yd in sorted(recent.items()))
            print(f'    Recents: {row}')
    print()
    def fix(obj):
        if isinstance(obj,dict): return {str(k):fix(v) for k,v in obj.items()}
        if isinstance(obj,list): return [fix(v) for v in obj]
        if isinstance(obj,(np.integer,)): return int(obj)
        if isinstance(obj,(np.floating,)): return float(obj)
        if isinstance(obj,pd.Timestamp): return str(obj)
        return obj
    with open(OUT_DIR/f't6g_{ticker.lower().replace("^","")}_validation.json','w') as f:
        json.dump(fix(r), f, indent=2, default=str)

# Taula comparativa
REF = {'MSFT':('ACCEPTED_D1_ASSET',41,78.0,3.46,12.7,0.0,'10/12',100.0,0.75),
       'NVDA':('WATCHLIST',68,63.2,1.61,6.0,4.4,'11/13',100.0,1.55),
       'QQQ': ('WATCHLIST',40,62.5,1.53,3.56,2.5,'7/8',100.0,1.32)}
print(f'{"="*90}\nTAULA COMPARATIVA — T6g vs referència T6e\n{"="*90}')
print(f'{"Ticker":<10}{"N":>5}{"WR_b":>7}{"EV@20x":>9}{"Liq":>7}{"WF":>8}{"MC":>6}{"MAE":>6}  {"Status"}')
print('─'*90)
for tk,(st,n,wr,pf,ev,liq,wf,mc,mae) in REF.items():
    print(f'{tk:<10}{n:>5}{wr:>6.0f}%{ev:>+8.1f}${liq:>6.1f}%{wf:>8}{mc:>5.0f}%{mae:>5.2f}%  {st}')
print('·'*90)
for ticker,r in sorted(results.items(), key=lambda x:-x[1].get('ev_dep',-99)):
    print(f'{ticker:<10}{r["n"]:>5}{r["wr_base"]:>6.0f}%{r["ev_dep"]:>+8.1f}${r["liq_pct"]:>6.1f}%'
          f'{r["wf"]:>8}{r["mc"]:>5.0f}%{r["mae_med"]:>5.2f}%  {r["status"]}')

new_acc = [t for t,r in results.items() if r['status']=='ACCEPTED_D1_ASSET']
new_wl  = [t for t,r in results.items() if r['status']=='WATCHLIST']
print(f'\n  Nous ACCEPTED: {new_acc or "cap"}')
print(f'  Nous WATCHLIST: {new_wl or "cap"}')

# CSV
rows = []
for tk,(st,n,wr,pf,ev,liq,wf,mc,mae) in REF.items():
    rows.append({'ticker':tk,'source':'T6e','n':n,'ev_dep':ev,'liq_pct':liq,'wf':wf,'mc':mc,'mae_med':mae,'status':st})
for tk,r in results.items():
    rows.append({'ticker':tk,'source':'T6g','n':r['n'],'ev_dep':r['ev_dep'],'liq_pct':r['liq_pct'],
                 'wf':r['wf'],'mc':r['mc'],'mae_med':r['mae_med'],'status':r['status']})
csv_path = OUT_DIR/'t6g_commodities_indices_comparison.csv'
with open(csv_path,'w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=['ticker','source','n','ev_dep','liq_pct','wf','mc','mae_med','status'])
    w.writeheader(); w.writerows(rows)
print(f'\n  CSV: {csv_path}')
