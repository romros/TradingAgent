"""
T6f — Screening final d'actius addicionals per capitulation_d1

Objectiu:
  Determinar si hi ha actius nous del mismo terreny (equitats D1)
  que passin el gate ACCEPTED_D1_ASSET o WATCHLIST definit a T6e.

Setup: capitulation_d1 (body < -2% + close < BB_lower(20,2)) — sense canvis
Gate D1: lab/docs/D1_GATE_CRITERIA.md
Actius nous: AMD, NFLX + reconfirmar META, GOOGL, AMZN (ja REJECTED a T6d)
Referència: MSFT (ACCEPTED), NVDA (WATCHLIST), QQQ (WATCHLIST)

Executar: python3 lab/studies/t6f_capitulation_d1_asset_screen.py
"""
from __future__ import annotations

import sys
import csv
import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

OUT_DIR = PROJECT_ROOT / 'lab' / 'out'
OUT_DIR.mkdir(exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
FEE = 5.38
CAPITAL = 250.0
COL_PCT = 0.20
COL_MAX = 60.0
COL_MIN = 15.0
LEV = 20
YEARS_BACK = 13

# Gate D1 per asset (T6e)
GATE_D1 = {
    'N_min': 35,
    'WR_min': 60.0,
    'EV_min': 8.0,
    'PF_min': 1.8,
    'liq_max': 5.0,
    'WF_min': 70.0,
    'MC_min': 90.0,
    'MAE_max': 1.5,
}

# Actius a testar (nous) + referència (ja validats a T6d/T6e)
NEW_ASSETS = ['AMD', 'NFLX', 'META', 'GOOGL', 'AMZN']
REF_ASSETS = {
    'MSFT': {'n': 41, 'wr': 78.0, 'ev': 12.7, 'pf': 3.46, 'liq': 0.0,
             'wf': '10/12', 'wf_pct': 83.3, 'mc': 100.0, 'mae': 0.75,
             'status': 'ACCEPTED_D1_ASSET'},
    'NVDA': {'n': 68, 'wr': 63.2, 'ev': 6.0, 'pf': 1.61, 'liq': 4.4,
             'wf': '11/13', 'wf_pct': 84.6, 'mc': 100.0, 'mae': 1.55,
             'status': 'WATCHLIST'},
    'QQQ':  {'n': 40, 'wr': 62.5, 'ev': 3.56, 'pf': 1.53, 'liq': 2.5,
             'wf': '7/8', 'wf_pct': 87.5, 'mc': 100.0, 'mae': 1.32,
             'status': 'WATCHLIST'},
}

# ── Data download ──────────────────────────────────────────────────────────────
def download_d1(ticker: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
        end = datetime.now(timezone.utc)
        start = end.replace(year=end.year - YEARS_BACK)
        df = yf.download(ticker, start=start.strftime('%Y-%m-%d'),
                         end=end.strftime('%Y-%m-%d'), interval='1d',
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[['Open', 'High', 'Low', 'Close']].copy()
        df.columns = ['O', 'H', 'L', 'C']
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.dropna()
    except Exception as e:
        print(f'  [WARN] {ticker}: {e}')
        return None


# ── Signal: capitulation_d1 (idèntic a T6d, sense canvis) ─────────────────────
def gen_capitulation_d1(df: pd.DataFrame, body_thresh: float = -0.02) -> list:
    C, O, H, L = df['C'].values, df['O'].values, df['H'].values, df['L'].values
    N = len(C)
    bb_lo = np.full(N, np.nan)
    for i in range(19, N):
        w = C[i - 19:i + 1]
        bb_lo[i] = w.mean() - 2 * w.std(ddof=0)
    body_pct = (C - O) / np.maximum(O, 1e-9)
    trades = []
    for i in range(50, N - 1):
        if body_pct[i] >= body_thresh:
            continue
        if np.isnan(bb_lo[i]) or C[i] >= bb_lo[i]:
            continue
        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        trades.append({
            'ts': df.index[i + 1], 'yr': df.index[i + 1].year,
            'move': (c1 - o1) / o1,
            'mae':  (o1 - l1) / o1,
            'mfe':  (h1 - o1) / o1,
        })
    return trades


# ── Validation (inline, idèntic a T6d) ────────────────────────────────────────
def validate(ticker: str, trades: list) -> dict:
    if not trades:
        return {'ticker': ticker, 'n': 0, 'status': 'REJECTED', 'reason': 'no_trades'}

    moves = np.array([t['move'] for t in trades])
    maes  = np.array([t['mae']  for t in trades])
    mfes  = np.array([t['mfe']  for t in trades])
    years = np.array([t['yr']   for t in trades])
    N = len(moves)

    # ── Baseline ──
    pnl_base = 4000.0 * moves
    wr_base = 100 * np.mean(pnl_base > 0)
    w, l = pnl_base[pnl_base > 0], pnl_base[pnl_base <= 0]
    pf_base = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99.0

    # ── Deployable @ 20x ──
    liq_th = 1.0 / LEV
    cap = CAPITAL
    deploy_pnls = []
    for i in range(N):
        col = min(max(cap * COL_PCT, COL_MIN), COL_MAX)
        if cap < COL_MIN:
            break
        nom = col * LEV
        pnl = (-col - FEE) if maes[i] >= liq_th else (nom * moves[i] - FEE)
        deploy_pnls.append(pnl)
        cap = max(0, cap + pnl)
    dp = np.array(deploy_pnls)
    liq_rate = 100 * np.mean(maes >= liq_th)
    wr_dep = 100 * np.mean(dp > 0) if len(dp) > 0 else 0
    wd, ld = dp[dp > 0], dp[dp <= 0]
    pf_dep = abs(wd.sum() / ld.sum()) if len(ld) > 0 and ld.sum() != 0 else 99.0
    ev_dep = float(np.mean(dp)) if len(dp) > 0 else 0.0
    cap_final = float(cap)

    # MaxDD
    eq = [CAPITAL]
    for p in deploy_pnls:
        eq.append(eq[-1] + p)
    peak = eq[0]
    mdd = 0.0
    for e in eq:
        if e > peak:
            peak = e
        dd = (peak - e) / peak if peak > 0 else 0
        mdd = max(mdd, dd)

    mae_med = round(100 * float(np.median(maes)), 2)
    mfe_med = round(100 * float(np.median(mfes)), 2)

    # ── MC shuffle ──
    mc = round(100 * sum(1 for _ in range(2000) if np.sum(np.random.permutation(moves)) > 0) / 2000, 1)

    # ── WF per any ──
    unique_yrs = sorted(set(years))
    wf_pos = 0
    yearly = {}
    for yr in unique_yrs:
        mask = years == yr
        yr_pnl = pnl_base[mask]
        if len(yr_pnl) == 0:
            continue
        total = float(yr_pnl.sum())
        yearly[yr] = {'n': int(mask.sum()), 'wr': round(100 * float(np.mean(yr_pnl > 0)), 1),
                      'total': round(total, 1)}
        if total > 0:
            wf_pos += 1
    wf_str = f'{wf_pos}/{len(unique_yrs)}'
    wf_pct = 100 * wf_pos / max(len(unique_yrs), 1)

    span = max(unique_yrs) - min(unique_yrs) + 1 if len(unique_yrs) > 1 else 1
    tpy = round(N / span, 1)

    # ── Gate D1 check ──
    gate = GATE_D1
    criteria = {
        'N':   N >= gate['N_min'],
        'WR':  wr_base >= gate['WR_min'],
        'EV':  ev_dep >= gate['EV_min'],
        'PF':  pf_dep >= gate['PF_min'],
        'liq': liq_rate <= gate['liq_max'],
        'WF':  wf_pct >= gate['WF_min'],
        'MC':  mc >= gate['MC_min'],
        'MAE': mae_med <= gate['MAE_max'],
    }
    n_pass = sum(criteria.values())

    # Classify
    if N < 20 or mc < 90 or wf_pct < 60 or ev_dep <= 0:
        status = 'REJECTED'
        if N < 20:
            reason = f'N={N} < 20'
        elif mc < 90:
            reason = f'MC {mc}% < 90%'
        elif wf_pct < 60:
            reason = f'WF {wf_pct:.0f}% < 60%'
        else:
            reason = f'EV {ev_dep:.1f}$ ≤ 0'
    elif n_pass == 8:
        status = 'ACCEPTED_D1_ASSET'
        reason = 'Passes all 8 D1 gate criteria'
    elif n_pass >= 5 and criteria['MC'] and criteria['WF']:
        status = 'WATCHLIST'
        fails = [k for k, v in criteria.items() if not v]
        reason = f'{n_pass}/8 criteria. Fails: {", ".join(fails)}'
    else:
        status = 'REJECTED'
        fails = [k for k, v in criteria.items() if not v]
        reason = f'{n_pass}/8 criteria, fails: {", ".join(fails)}'

    return {
        'ticker': ticker,
        'n': N,
        'tpy': tpy,
        'wr_base': round(wr_base, 1),
        'pf_base': round(pf_base, 2),
        'ev_dep': round(ev_dep, 2),
        'pf_dep': round(pf_dep, 2),
        'liq_pct': round(liq_rate, 1),
        'cap_final': round(cap_final, 0),
        'mdd_pct': round(100 * mdd, 1),
        'mae_med': mae_med,
        'mfe_med': mfe_med,
        'mc': mc,
        'wf': wf_str,
        'wf_pct': round(wf_pct, 1),
        'criteria': criteria,
        'criteria_pass': n_pass,
        'yearly': yearly,
        'status': status,
        'reason': reason,
    }


# ── Main ───────────────────────────────────────────────────────────────────────
print(f'\n{"="*95}')
print('T6f — SCREENING FINAL: capitulation_d1 × nous actius')
print(f'Gate D1: N≥{GATE_D1["N_min"]} WR≥{GATE_D1["WR_min"]}% EV≥+{GATE_D1["EV_min"]}$ '
      f'PF≥{GATE_D1["PF_min"]} liq≤{GATE_D1["liq_max"]}% WF≥{GATE_D1["WF_min"]}% '
      f'MC≥{GATE_D1["MC_min"]}% MAE≤{GATE_D1["MAE_max"]}%')
print(f'{"="*95}\n')

new_results = {}

for ticker in NEW_ASSETS:
    print(f'  Descarregant {ticker}... ', end='', flush=True)
    df = download_d1(ticker)
    if df is None or len(df) < 100:
        print('NO DATA')
        continue
    n_yrs = (df.index[-1] - df.index[0]).days / 365.25
    print(f'{len(df)} candles D1 ({n_yrs:.1f} anys)')
    trades = gen_capitulation_d1(df)
    res = validate(ticker, trades)
    new_results[ticker] = res

print()

# ── Detailed output per new asset ──────────────────────────────────────────────
for ticker, r in new_results.items():
    cr = r.get('criteria', {})
    flags = {k: '✓' if v else '✗' for k, v in cr.items()} if cr else {}
    print(f'  ── {ticker} ──')
    print(f'    N={r["n"]} ({r["tpy"]}t/any) | WR_base={r["wr_base"]}% | '
          f'PF_base={r["pf_base"]}')
    print(f'    Deploy 20x: EV={r["ev_dep"]:+.1f}$  PF={r["pf_dep"]}  '
          f'liq={r["liq_pct"]}%  cap={r["cap_final"]}$  MaxDD={r["mdd_pct"]}%')
    print(f'    MAE med={r["mae_med"]}%  MFE med={r["mfe_med"]}%')
    print(f'    MC={r["mc"]}%  WF={r["wf"]} ({r["wf_pct"]}%)')
    if flags:
        gate_line = '  '.join(f'{k}:{flags[k]}' for k in ['N','WR','EV','PF','liq','WF','MC','MAE'])
        print(f'    Gate: {gate_line}  ({r["criteria_pass"]}/8)')
    print(f'    → {r["status"]} — {r["reason"]}')
    if r.get('yearly'):
        recent = {yr: yd for yr, yd in sorted(r['yearly'].items()) if yr >= 2020}
        if recent:
            row = '  '.join(f"{yr}:{yd['n']}t/{yd['wr']:.0f}%/{yd['total']:+.0f}$"
                            for yr, yd in sorted(recent.items()))
            print(f'    Recents: {row}')
    print()

    # Save artifact
    def fix(obj):
        if isinstance(obj, dict): return {str(k): fix(v) for k, v in obj.items()}
        if isinstance(obj, list): return [fix(v) for v in obj]
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, pd.Timestamp): return str(obj)
        return obj

    art_path = OUT_DIR / f't6f_{ticker.lower()}_validation.json'
    with open(art_path, 'w') as f:
        json.dump(fix(r), f, indent=2, default=str)

# ── Comparative table (nous + referència) ──────────────────────────────────────
print(f'\n{"="*95}')
print('TAULA COMPARATIVA T6f (nous actius + referència T6e)')
print(f'{"="*95}')
print(f'{"Ticker":<8} {"Src":<5} {"N":>5} {"WR_b":>6} {"PF_b":>6} {"EV@20x":>8} '
      f'{"Liq":>6} {"WF":>7} {"MC":>5} {"MAE":>6} {"Pass":>5} {"Status":<20}')
print(f'{"─"*95}')

# Referència (T6e)
for tk, r in REF_ASSETS.items():
    wf_pos, wf_tot = map(int, r['wf'].split('/'))
    wf_pct = 100 * wf_pos / wf_tot
    print(f'{tk:<8} {"T6e":<5} {r["n"]:>5} {r["wr"]:>5.0f}% {r["pf"]:>5.2f} '
          f'{r["ev"]:>+7.1f}$ {r["liq"]:>5.1f}% {r["wf"]:>7} '
          f'{r["mc"]:>4.0f}% {r["mae"]:>5.2f}%  8/8  {r["status"]:<20}')

print(f'{"·"*95}')

# Nous
for ticker, r in sorted(new_results.items(), key=lambda x: -x[1].get('ev_dep', -99)):
    n_pass = r.get('criteria_pass', 0)
    print(f'{ticker:<8} {"T6f":<5} {r["n"]:>5} {r["wr_base"]:>5.0f}% {r["pf_dep"]:>5.2f} '
          f'{r["ev_dep"]:>+7.1f}$ {r["liq_pct"]:>5.1f}% {r["wf"]:>7} '
          f'{r["mc"]:>4.0f}% {r["mae_med"]:>5.2f}%  {n_pass}/8  {r["status"]:<20}')

# ── Summary ────────────────────────────────────────────────────────────────────
new_accepted = [t for t, r in new_results.items() if r['status'] == 'ACCEPTED_D1_ASSET']
new_watchlist = [t for t, r in new_results.items() if r['status'] == 'WATCHLIST']
new_rejected  = [t for t, r in new_results.items() if r['status'] == 'REJECTED']

print(f'\n  Nous: {len(new_accepted)} ACCEPTED_D1_ASSET, '
      f'{len(new_watchlist)} WATCHLIST, {len(new_rejected)} REJECTED')
if new_accepted:
    print(f'  Nous ACCEPTED: {", ".join(new_accepted)}')
if new_watchlist:
    print(f'  Nous WATCHLIST: {", ".join(new_watchlist)}')

# ── Probe universe recommendation ─────────────────────────────────────────────
print(f'\n{"="*95}')
print('UNIVERS RECOMANAT PER AL PAPER PROBE')
print(f'{"="*95}')

all_accepted = ['MSFT'] + new_accepted
all_watchlist = ['NVDA', 'QQQ'] + new_watchlist

print(f'\n  ACCEPTED_D1_ASSET: {", ".join(all_accepted)}')
print(f'  WATCHLIST útils:   {", ".join(all_watchlist)}')
print()

if len(all_accepted) == 1 and all_accepted[0] == 'MSFT':
    print('  → Portfolio estret: MSFT és el pillar, NVDA i QQQ com a diversificació temporal')
    print('  → Paper probe: MSFT-centric (asset primari) + NVDA/QQQ opcionals')
    probe_type = 'MSFT_CENTRIC'
elif len(all_accepted) >= 2:
    print(f'  → Portfolio ampliat: {len(all_accepted)} assets ACCEPTED_D1_ASSET')
    print(f'  → Paper probe: multi-asset ({", ".join(all_accepted)})')
    probe_type = 'MULTI_ASSET'
else:
    probe_type = 'MSFT_CENTRIC'

print(f'\n  Recomanació final: {probe_type}')

# ── CSV comparatiu ─────────────────────────────────────────────────────────────
csv_path = OUT_DIR / 't6f_d1_asset_screen_comparison.csv'
fieldnames = ['ticker', 'source', 'n', 'tpy', 'wr_base', 'pf_dep', 'ev_dep',
              'liq_pct', 'wf', 'mc', 'mae_med', 'criteria_pass', 'status']
rows = []
for tk, r in REF_ASSETS.items():
    wf_pos, wf_tot = map(int, r['wf'].split('/'))
    rows.append({'ticker': tk, 'source': 'T6e', 'n': r['n'], 'tpy': '—',
                 'wr_base': r['wr'], 'pf_dep': r['pf'], 'ev_dep': r['ev'],
                 'liq_pct': r['liq'], 'wf': r['wf'], 'mc': r['mc'],
                 'mae_med': r['mae'], 'criteria_pass': '8/8', 'status': r['status']})
for tk, r in new_results.items():
    rows.append({'ticker': tk, 'source': 'T6f', 'n': r['n'], 'tpy': r['tpy'],
                 'wr_base': r['wr_base'], 'pf_dep': r['pf_dep'], 'ev_dep': r['ev_dep'],
                 'liq_pct': r['liq_pct'], 'wf': r['wf'], 'mc': r['mc'],
                 'mae_med': r['mae_med'], 'criteria_pass': f'{r["criteria_pass"]}/8',
                 'status': r['status']})

with open(csv_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f'\n  CSV guardat: {csv_path}')
print(f'  Artifacts JSON: {OUT_DIR}/t6f_<ticker>_validation.json')
