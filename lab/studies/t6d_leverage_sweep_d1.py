"""
T6d — Leverage sweep per assets D1 + nous assets Ostium

Objectiu:
  1. Per cada asset WATCHLIST (Nasdaq, NVDA, MSFT), trobar leverage òptim
  2. Explorar nous assets Ostium perps: SPY, AMZN, META, GOOGL, TSLA, AAPL
  3. Identificar quins actius passen el gate ACCEPTED a cap leverage

Setup: Capitulation D1 (body < -2% + close < BB_lower(20,2))
Leverages testats: 5x, 10x, 15x, 20x, 25x, 30x

Executar: python3 lab/studies/t6d_leverage_sweep_d1.py
"""
from __future__ import annotations

import sys
import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

warnings.filterwarnings('ignore')

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

OUT_DIR = PROJECT_ROOT / 'lab' / 'out'
OUT_DIR.mkdir(exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
FEE = 5.38          # $ per trade (Ostium open+close 0.06% each side, 4000$ nom)
CAPITAL = 250.0
COL_PCT = 0.20      # 20% of capital per trade
COL_MIN = 15.0
COL_MAX = 60.0
NOM_BASE = 4000.0   # nominal for baseline (no leverage)

LEVERAGES = [5, 10, 15, 20, 25, 30]
LEV_DEPLOY = 20     # canonical deployable leverage

# Ostium perps catalog (D1 equity candidates)
EQUITY_ASSETS = {
    'QQQ':   'QQQ',    # Nasdaq 100 ETF
    'SPY':   'SPY',    # S&P 500 ETF
    'NVDA':  'NVDA',
    'MSFT':  'MSFT',
    'AAPL':  'AAPL',
    'AMZN':  'AMZN',
    'META':  'META',
    'GOOGL': 'GOOGL',
    'TSLA':  'TSLA',
    'GLD':   'GLD',    # Gold ETF (Ostium té XAU/USD)
}

# ── Data download ──────────────────────────────────────────────────────────────
def download_d1(ticker: str, years: int = 12) -> pd.DataFrame | None:
    """Download D1 OHLCV via yfinance. Returns df with O/H/L/C/V columns."""
    try:
        import yfinance as yf
        end = datetime.now(timezone.utc)
        start = end.replace(year=end.year - years)
        df = yf.download(ticker, start=start.strftime('%Y-%m-%d'),
                         end=end.strftime('%Y-%m-%d'), interval='1d',
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.columns = ['O', 'H', 'L', 'C', 'V']
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize(None)
        df = df.dropna()
        return df
    except Exception as e:
        print(f'  [WARN] {ticker}: {e}')
        return None


# ── Indicators ─────────────────────────────────────────────────────────────────
def compute_d1_indicators(df: pd.DataFrame) -> dict:
    C = df['C'].values
    O = df['O'].values
    H = df['H'].values
    L = df['L'].values
    V = df['V'].values
    N = len(C)

    # Bollinger Bands (20, 2)
    bb_lo = np.full(N, np.nan)
    bb_hi = np.full(N, np.nan)
    for i in range(19, N):
        w = C[i - 19:i + 1]
        mu = np.mean(w)
        sd = np.std(w, ddof=0)
        bb_lo[i] = mu - 2 * sd
        bb_hi[i] = mu + 2 * sd

    # RSI Wilder (7)
    rsi7 = np.full(N, np.nan)
    d = np.diff(C)
    if len(d) >= 7:
        g = np.where(d > 0, d, 0.0)
        lo = np.where(d < 0, -d, 0.0)
        ag = np.mean(g[:7])
        al = np.mean(lo[:7])
        rsi7[7] = 100 - 100 / (1 + ag / al) if al != 0 else 100.0
        for i in range(7, len(d)):
            ag = (ag * 6 + g[i]) / 7
            al = (al * 6 + lo[i]) / 7
            rsi7[i + 1] = 100 - 100 / (1 + ag / al) if al != 0 else 100.0

    # Drop 3 candles (3 business days)
    drop3 = np.zeros(N)
    for i in range(3, N):
        drop3[i] = (C[i] - C[i - 3]) / C[i - 3]

    # Volume relative
    vol_ma = pd.Series(V).rolling(20).mean().values
    vol_rel = V / np.maximum(vol_ma, 1)

    # Body pct
    body_pct = (C - O) / np.maximum(O, 1e-9)

    return {
        'bb_lo': bb_lo, 'bb_hi': bb_hi,
        'rsi7': rsi7,
        'drop3': drop3,
        'vol_rel': vol_rel,
        'body_pct': body_pct,
    }


# ── Signal generator ───────────────────────────────────────────────────────────
def gen_capitulation_d1(df: pd.DataFrame, ind: dict, body_thresh: float = -0.02) -> list:
    """
    Capitulation D1: body < body_thresh + close < BB_lower(20,2)
    Entry: open of next candle
    Exit: close of next candle (1 candle hold)
    """
    C = df['C'].values
    O = df['O'].values
    H = df['H'].values
    L = df['L'].values
    N = len(df)
    body_pct = ind['body_pct']
    bb_lo = ind['bb_lo']

    trades = []
    for i in range(50, N - 1):
        if body_pct[i] >= body_thresh:
            continue
        if np.isnan(bb_lo[i]) or C[i] >= bb_lo[i]:
            continue

        o1 = O[i + 1]
        h1 = H[i + 1]
        l1 = L[i + 1]
        c1 = C[i + 1]

        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1

        trades.append({
            'ts': df.index[i + 1],
            'yr': df.index[i + 1].year,
            'asset': '',
            'move': move,
            'mae': mae,
            'mfe': mfe,
        })
    return trades


# ── Validation per leverage ────────────────────────────────────────────────────
def eval_at_leverage(moves: np.ndarray, maes: np.ndarray, mfes: np.ndarray,
                     years: np.ndarray, leverage: int) -> dict:
    N = len(moves)
    liq_th = 1.0 / leverage

    # Deployable with liquidation + fees
    cap = CAPITAL
    deploy_pnls = []
    for i in range(N):
        col = min(max(cap * COL_PCT, COL_MIN), COL_MAX)
        if cap < COL_MIN:
            break
        nom = col * leverage
        if maes[i] >= liq_th:
            pnl = -col - FEE
        else:
            pnl = nom * moves[i] - FEE
        deploy_pnls.append(pnl)
        cap += pnl
        if cap < 0:
            cap = 0

    dp = np.array(deploy_pnls)
    liq_rate = 100 * np.mean(maes >= liq_th)

    if len(dp) == 0:
        return {'lev': leverage, 'liq': 0, 'wr': 0, 'pf': 0, 'ev': -99, 'cap': 0, 'mdd': 100}

    wr = 100 * np.mean(dp > 0)
    w = dp[dp > 0]
    l = dp[dp <= 0]
    pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99.0
    ev = np.mean(dp)
    final_cap = cap

    # Max drawdown
    eq = [CAPITAL]
    for p in deploy_pnls:
        eq.append(eq[-1] + p)
    peak = eq[0]
    mdd = 0
    for e in eq:
        if e > peak:
            peak = e
        dd = (peak - e) / peak if peak > 0 else 0
        mdd = max(mdd, dd)

    return {
        'lev': leverage,
        'liq': round(liq_rate, 1),
        'wr': round(wr, 1),
        'pf': round(pf, 2),
        'ev': round(ev, 2),
        'cap': round(final_cap, 0),
        'mdd': round(100 * mdd, 1),
    }


def validate_asset(name: str, trades: list) -> dict:
    """Full validation: baseline + MC + WF + leverage sweep."""
    if not trades:
        return {'name': name, 'n': 0, 'status': 'REJECTED', 'reason': 'no_trades'}

    moves = np.array([t['move'] for t in trades])
    maes = np.array([t['mae'] for t in trades])
    mfes = np.array([t['mfe'] for t in trades])
    years = np.array([t['yr'] for t in trades])
    N = len(moves)

    # ── Baseline (no fees, no liq) ──
    pnl_base = NOM_BASE * moves
    wr_base = 100 * np.mean(pnl_base > 0)
    w = pnl_base[pnl_base > 0]
    l = pnl_base[pnl_base <= 0]
    pf_base = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99.0
    ev_base = np.mean(pnl_base)

    # ── MFE/MAE ──
    mae_med = round(100 * np.median(maes), 2)
    mfe_med = round(100 * np.median(mfes), 2)

    # ── Leverage sweep ──
    lev_results = {}
    for lev in LEVERAGES:
        lev_results[lev] = eval_at_leverage(moves, maes, mfes, years, lev)

    deploy = lev_results[LEV_DEPLOY]

    # ── Best leverage (max EV, liq < 15%) ──
    best_lev = LEV_DEPLOY
    best_ev = deploy['ev']
    for lev, r in lev_results.items():
        if r['liq'] < 15.0 and r['ev'] > best_ev:
            best_ev = r['ev']
            best_lev = lev

    # ── Monte Carlo shuffle ──
    n_sims = 1000
    mc_profits = sum(1 for _ in range(n_sims) if np.sum(np.random.permutation(moves)) > 0)
    mc_shuffle = round(100 * mc_profits / n_sims, 1)

    # ── Walk-forward per year ──
    unique_yrs = sorted(set(years))
    yearly = {}
    wf_pos = 0
    for yr in unique_yrs:
        mask = years == yr
        yr_pnl = pnl_base[mask]
        if len(yr_pnl) == 0:
            continue
        total = yr_pnl.sum()
        yearly[yr] = {'n': int(mask.sum()), 'wr': round(100 * np.mean(yr_pnl > 0), 1),
                      'total': round(total, 1)}
        if total > 0:
            wf_pos += 1
    wf_str = f'{wf_pos}/{len(unique_yrs)}'

    # Trades per year
    span = max(unique_yrs) - min(unique_yrs) + 1 if len(unique_yrs) > 1 else 1
    tpy = round(N / span, 1)

    # ── Classify at best leverage ──
    best_r = lev_results[best_lev]
    status = 'REJECTED'
    reason = ''
    if N < 20:
        reason = f'N={N} < 20'
    elif mc_shuffle < 70:
        reason = f'MC shuffle {mc_shuffle}% < 70%'
    elif pf_base < 1.10:
        reason = f'PF baseline {pf_base:.2f} < 1.10'
    elif best_r['ev'] <= 0:
        reason = f'EV {best_r["ev"]:.1f}$ <= 0 (best lev {best_lev}x)'
    elif N >= 40 and best_r['ev'] >= 3 and mc_shuffle >= 80:
        status = 'WATCHLIST'
        reason = f'edge viable @ {best_lev}x'
    else:
        reason = 'edge insuficient'

    if (status == 'WATCHLIST' and N >= 120 and tpy >= 10 and best_r['ev'] >= 8
            and best_r['pf'] >= 1.30 and mc_shuffle >= 90 and wf_pos / max(len(unique_yrs), 1) >= 0.60):
        status = 'ACCEPTED'
        reason = f'ACCEPTED @ {best_lev}x'

    return {
        'name': name,
        'n': N,
        'tpy': tpy,
        'baseline': {'wr': round(wr_base, 1), 'pf': round(pf_base, 2), 'ev': round(ev_base, 1)},
        'mae_median': mae_med,
        'mfe_median': mfe_med,
        'mc_shuffle': mc_shuffle,
        'wf': wf_str,
        'lev_sweep': lev_results,
        'deploy_20x': deploy,
        'best_lev': best_lev,
        'best_ev': round(best_ev, 2),
        'yearly': yearly,
        'status': status,
        'reason': reason,
    }


# ── Main ───────────────────────────────────────────────────────────────────────
print(f'\n{"="*90}')
print('T6d — LEVERAGE SWEEP D1 + NOUS ASSETS OSTIUM')
print(f'Setup: Capitulation D1 (body < -2% + close < BB_lower)')
print(f'Leverages: {LEVERAGES}  |  Fee per trade: {FEE}$  |  Capital: {CAPITAL}$')
print(f'{"="*90}\n')

all_results = []
cache = {}

for ticker, label in EQUITY_ASSETS.items():
    print(f'  Descarregant {ticker}... ', end='', flush=True)
    df = download_d1(ticker, years=12)
    if df is None or len(df) < 100:
        print(f'NO DATA')
        continue
    cache[ticker] = df
    n_years = (df.index[-1] - df.index[0]).days / 365.25
    print(f'{len(df)} candles D1 ({n_years:.1f} anys)')

print()

for ticker, df in cache.items():
    ind = compute_d1_indicators(df)
    trades = gen_capitulation_d1(df, ind, body_thresh=-0.02)
    for t in trades:
        t['asset'] = ticker
    res = validate_asset(ticker, trades)
    all_results.append(res)

    b = res['baseline']
    d = res['deploy_20x']
    lev_s = res['lev_sweep']
    print(f'\n  ── {ticker} (N={res["n"]}, {res["tpy"]}t/any) ──')
    print(f'    Baseline:  WR={b["wr"]}%  PF={b["pf"]}  EV={b["ev"]:+.1f}$')
    print(f'    Deploy 20x: WR={d["wr"]}%  PF={d["pf"]}  EV={d["ev"]:+.1f}$  Liq={d["liq"]}%  MaxDD={d["mdd"]}%')
    print(f'    MAE mediana: {res["mae_median"]}%  (liq @ 20x si MAE≥5%)')
    print(f'    MC shuffle: {res["mc_shuffle"]}%')
    print(f'    WF: {res["wf"]} anys positius')
    print(f'    Best lev: {res["best_lev"]}x  EV={res["best_ev"]:+.1f}$')
    print(f'    → STATUS: {res["status"]} ({res["reason"]})')

    # Leverage sweep table
    print(f'    {"Lev":>5}  {"Liq%":>6}  {"WR%":>5}  {"PF":>5}  {"EV$":>7}  {"Cap$":>7}  {"MDD%":>6}')
    for lev in LEVERAGES:
        lr = lev_s[lev]
        marker = ' ←' if lev == res['best_lev'] else ''
        print(f'    {lr["lev"]:>4}x  {lr["liq"]:>5.1f}%  {lr["wr"]:>4.0f}%  '
              f'{lr["pf"]:>5.2f}  {lr["ev"]:>+6.1f}$  {lr["cap"]:>6.0f}$  '
              f'{lr["mdd"]:>5.1f}%{marker}')

    # Yearly breakdown
    if res.get('yearly'):
        yrs = sorted(res['yearly'].items())
        recent = [(yr, yd) for yr, yd in yrs if yr >= 2021]
        if recent:
            print(f'    Recents: ' + '  '.join(
                f'{yr}:{yd["n"]}t/{yd["wr"]:.0f}%/{yd["total"]:+.0f}$' for yr, yd in recent))

# ── Combined: WATCHLIST + ACCEPTED a qualsevol leverage ────────────────────────
print(f'\n\n{"="*90}')
print('TAULA COMPARATIVA T6d — Assets D1')
print(f'{"="*90}')
print(f'{"Asset":<8} {"N":>5} {"t/yr":>6} {"WR_b":>6} {"PF_b":>6} '
      f'{"MC%":>5} {"WF":>6} {"EV@20x":>8} {"Liq@20x":>8} '
      f'{"BestLev":>8} {"EV@best":>8} {"Status":<12}')
print(f'{"─"*90}')

for r in sorted(all_results, key=lambda x: -x.get('best_ev', -99)):
    b = r['baseline']
    d = r['deploy_20x']
    print(f'{r["name"]:<8} {r["n"]:>5} {r["tpy"]:>5.1f} '
          f'{b["wr"]:>5.0f}% {b["pf"]:>5.2f} '
          f'{r["mc_shuffle"]:>4.0f}% {r["wf"]:>6} '
          f'{d["ev"]:>+7.1f}$ {d["liq"]:>6.1f}% '
          f'{r["best_lev"]:>6}x {r["best_ev"]:>+7.1f}$ '
          f'{r["status"]:<12}')

accepted = [r for r in all_results if r['status'] == 'ACCEPTED']
watchlist = [r for r in all_results if r['status'] == 'WATCHLIST']
rejected = [r for r in all_results if r['status'] == 'REJECTED']

print(f'\n  RESUM: {len(accepted)} ACCEPTED, {len(watchlist)} WATCHLIST, {len(rejected)} REJECTED')
if accepted:
    print(f'  ACCEPTED: {", ".join(r["name"] for r in accepted)}')
if watchlist:
    print(f'  WATCHLIST: {", ".join(r["name"] for r in watchlist)}')

# ── Candidate portfolio: top 3 ─────────────────────────────────────────────────
top = sorted(all_results, key=lambda x: -x.get('best_ev', -99))[:4]
print(f'\n  TOP CANDIDATS (per EV al leverage òptim):')
for r in top:
    if r['best_ev'] > 0:
        d20 = r['deploy_20x']
        print(f'    {r["name"]:<8}: N={r["n"]:>3}, best {r["best_lev"]}x → EV={r["best_ev"]:+.1f}$, '
              f'liq={d20["liq"]}%@20x, MC={r["mc_shuffle"]}%, WF={r["wf"]}')

# ── Decision input ─────────────────────────────────────────────────────────────
print(f'\n{"="*90}')
print('INPUTS PER A LA DECISIÓ')
print(f'{"="*90}')
print('  Gate ACCEPTED (per asset individual): N≥120, EV≥8$, PF≥1.30, MC≥90%, WF≥60%')
print('  Gate WATCHLIST: N≥40, EV≥3$, PF≥1.15, MC≥80%')
print()

can_build = False
for r in all_results:
    if r['status'] == 'ACCEPTED':
        can_build = True
        print(f'  ✓ {r["name"]} ACCEPTED → pot anar a BUILD directament')

if not can_build:
    print('  → Cap setup ACCEPTED individual.')
    wl_count = len(watchlist)
    print(f'  → {wl_count} WATCHLIST: {", ".join(r["name"] for r in watchlist)}')
    if wl_count >= 2:
        print('  → Opció: portfolio WATCHLIST combinat (redueix variança)')
    print('  → Cal PM decision: paper 4 setmanes + revalorar, o continuar LAB')

# ── Save artifacts ─────────────────────────────────────────────────────────────
def fix_types(obj):
    if isinstance(obj, dict):
        return {str(k): fix_types(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fix_types(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    return obj

artifact = {
    'task': 'T6d',
    'date': '2026-03-16',
    'setup': 'capitulation_d1 (body<-2% + close<BB_lower)',
    'leverages_tested': LEVERAGES,
    'results': fix_types(all_results),
    'summary': {
        'accepted': [r['name'] for r in accepted],
        'watchlist': [r['name'] for r in watchlist],
        'rejected': [r['name'] for r in rejected],
    }
}

artifact_path = OUT_DIR / 't6d_leverage_sweep_d1.json'
with open(artifact_path, 'w') as f:
    json.dump(artifact, f, indent=2, default=str)

print(f'\n  Artifact guardat: {artifact_path}')
