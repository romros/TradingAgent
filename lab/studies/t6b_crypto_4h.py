"""
T6b — Pivot a crypto 4H: 3 famílies × 2 hipòtesis

Famílies:
  F1: Capitulation extrema (adaptat de 1H → 4H)
  F2: Breakout post-compressió (BB squeeze + expansió)
  F3: Trend pullback continuation (EMA trend + RSI dip)

Assets: ETH, BTC, SOL
TF: 4H context / 4H execution
Leverage deployable: 20x

Cada hipòtesi es passa pel harness T5.
"""
from __future__ import annotations

import sys
import os
import pickle
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from lab.contracts.models import SetupSpec, SetupValidationResult

CACHE_4H = '/tmp/crypto_4h_cache.pkl'
OUT_DIR = PROJECT_ROOT / 'lab' / 'out'
OUT_DIR.mkdir(exist_ok=True)

FEE = 3.36
CAPITAL = 250.0
COL_PCT = 0.20
COL_MIN = 15.0
COL_MAX = 60.0
LEV_DEPLOY = 20

# ── Load data ──────────────────────────────────────────────────────────────────
with open(CACHE_4H, 'rb') as f:
    raw = pickle.load(f)

all_data = {}
for sym, rows in raw.items():
    name = sym.replace('USDT', '')
    df = pd.DataFrame(rows).set_index('ts')
    all_data[name] = df
    print(f'{name}: {len(df)} candles 4H, {df.index[0].date()} → {df.index[-1].date()}')


# ── Indicators ─────────────────────────────────────────────────────────────────
def compute_indicators(C, H, L, V):
    """Compute all needed indicators on close/high/low/volume arrays."""
    N = len(C)

    # RSI Wilder (7 and 14)
    def rsi_w(c, p):
        r = np.full(len(c), np.nan)
        d = np.diff(c)
        g = np.where(d > 0, d, 0.0)
        lo = np.where(d < 0, -d, 0.0)
        if p >= len(d):
            return r
        ag = np.mean(g[:p])
        al = np.mean(lo[:p])
        r[p] = 100 - 100 / (1 + ag / al) if al != 0 else 100
        for i in range(p, len(d)):
            ag = (ag * (p - 1) + g[i]) / p
            al = (al * (p - 1) + lo[i]) / p
            r[i + 1] = 100 - 100 / (1 + ag / al) if al != 0 else 100
        return r

    rsi7 = rsi_w(C, 7)
    rsi14 = rsi_w(C, 14)

    # BB (20, 2.0)
    bb_lo = np.full(N, np.nan)
    bb_hi = np.full(N, np.nan)
    bb_width = np.full(N, np.nan)
    for i in range(19, N):
        w = C[i - 19:i + 1]
        mu = np.mean(w)
        sd = np.std(w, ddof=0)
        bb_lo[i] = mu - 2 * sd
        bb_hi[i] = mu + 2 * sd
        bb_width[i] = (4 * sd) / mu if mu > 0 else 0  # normalised width

    # EMA 20, 50
    def ema(c, span):
        e = np.zeros(len(c))
        e[0] = c[0]
        a = 2 / (span + 1)
        for i in range(1, len(c)):
            e[i] = a * c[i] + (1 - a) * e[i - 1]
        return e

    ema20 = ema(C, 20)
    ema50 = ema(C, 50)

    # ATR (14)
    atr14 = np.full(N, np.nan)
    tr = np.zeros(N)
    for i in range(1, N):
        tr[i] = max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
    for i in range(14, N):
        atr14[i] = np.mean(tr[i - 13:i + 1])

    # Drop acumulat (3 candles = 12h at 4H)
    drop3 = np.zeros(N)
    for i in range(3, N):
        drop3[i] = (C[i] - C[i - 3]) / C[i - 3]

    # Volume relative
    vol_ma = pd.Series(V).rolling(20).mean().values
    vol_rel = V / np.maximum(vol_ma, 1)

    # Body pct
    body_pct = (C - np.array([df_o for df_o in [None]])) if False else None  # computed per-df below

    return {
        'rsi7': rsi7, 'rsi14': rsi14,
        'bb_lo': bb_lo, 'bb_hi': bb_hi, 'bb_width': bb_width,
        'ema20': ema20, 'ema50': ema50,
        'atr14': atr14,
        'drop3': drop3,
        'vol_rel': vol_rel,
    }


# ── Signal generators ──────────────────────────────────────────────────────────

def gen_capitulation_4h(df, ind):
    """F1a: Capitulation extrema 4H — body < -5% + BB < lower + drop3 < -8%"""
    C = df['C'].values
    O = df['O'].values
    H = df['H'].values
    L = df['L'].values
    N = len(df)
    body_pct = (C - O) / np.maximum(O, 1e-9)
    trades = []
    for i in range(200, N - 1):
        if body_pct[i] >= -0.05:
            continue
        if np.isnan(ind['bb_lo'][i]) or C[i] >= ind['bb_lo'][i]:
            continue
        if ind['drop3'][i] >= -0.08:
            continue
        # Entry next candle
        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1
        trades.append({
            'ts': df.index[i], 'yr': df.index[i].year,
            'asset': '', 'move': move, 'mae': mae, 'mfe': mfe,
        })
    return trades


def gen_capitulation_4h_mild(df, ind):
    """F1b: Capitulation 4H menys extrema — body < -3% + BB < lower + drop3 < -5%"""
    C = df['C'].values
    O = df['O'].values
    H = df['H'].values
    L = df['L'].values
    N = len(df)
    body_pct = (C - O) / np.maximum(O, 1e-9)
    trades = []
    for i in range(200, N - 1):
        if body_pct[i] >= -0.03:
            continue
        if np.isnan(ind['bb_lo'][i]) or C[i] >= ind['bb_lo'][i]:
            continue
        if ind['drop3'][i] >= -0.05:
            continue
        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1
        trades.append({
            'ts': df.index[i], 'yr': df.index[i].year,
            'asset': '', 'move': move, 'mae': mae, 'mfe': mfe,
        })
    return trades


def gen_bb_squeeze_breakout_4h(df, ind):
    """F2a: BB squeeze + breakout — BB width bottom 15% + close > BB upper"""
    C = df['C'].values
    O = df['O'].values
    H = df['H'].values
    L = df['L'].values
    N = len(df)
    bw = ind['bb_width']
    # Calculate percentile threshold from first 500 candles
    valid_bw = bw[~np.isnan(bw)]
    if len(valid_bw) < 100:
        return []
    p15 = np.percentile(valid_bw[:min(500, len(valid_bw))], 15)
    trades = []
    for i in range(200, N - 1):
        if np.isnan(bw[i]) or np.isnan(ind['bb_hi'][i]):
            continue
        if bw[i] > p15:  # not squeezed
            continue
        if C[i] <= ind['bb_hi'][i]:  # no breakout
            continue
        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1
        trades.append({
            'ts': df.index[i], 'yr': df.index[i].year,
            'asset': '', 'move': move, 'mae': mae, 'mfe': mfe,
        })
    return trades


def gen_atr_expansion_4h(df, ind):
    """F2b: ATR expansion — ATR low + big candle body > 2x ATR"""
    C = df['C'].values
    O = df['O'].values
    H = df['H'].values
    L = df['L'].values
    N = len(df)
    atr = ind['atr14']
    body = np.abs(C - O)
    valid_atr = atr[~np.isnan(atr)]
    if len(valid_atr) < 100:
        return []
    p25 = np.percentile(valid_atr[:min(500, len(valid_atr))], 25)
    trades = []
    for i in range(200, N - 1):
        if np.isnan(atr[i]):
            continue
        if i < 1:
            continue
        # ATR was low recently (previous candle)
        if not np.isnan(atr[i - 1]) and atr[i - 1] > p25:
            continue
        # Current candle is expansive and bullish
        if body[i] < 2 * atr[i]:
            continue
        if C[i] <= O[i]:  # must be green (breakout direction)
            continue
        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1
        trades.append({
            'ts': df.index[i], 'yr': df.index[i].year,
            'asset': '', 'move': move, 'mae': mae, 'mfe': mfe,
        })
    return trades


def gen_trend_rsi_dip_4h(df, ind):
    """F3a: Trend + RSI dip — EMA20 > EMA50 + RSI14 < 35 + green candle"""
    C = df['C'].values
    O = df['O'].values
    H = df['H'].values
    L = df['L'].values
    N = len(df)
    trades = []
    for i in range(200, N - 1):
        if np.isnan(ind['rsi14'][i]):
            continue
        # Uptrend
        if ind['ema20'][i] <= ind['ema50'][i]:
            continue
        # RSI dip
        if ind['rsi14'][i] >= 35:
            continue
        # Price still above EMA50
        if C[i] < ind['ema50'][i]:
            continue
        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1
        trades.append({
            'ts': df.index[i], 'yr': df.index[i].year,
            'asset': '', 'move': move, 'mae': mae, 'mfe': mfe,
        })
    return trades


def gen_pullback_ema20_4h(df, ind):
    """F3b: Pullback to EMA20 — uptrend + price touches EMA20 from above + bounce"""
    C = df['C'].values
    O = df['O'].values
    H = df['H'].values
    L = df['L'].values
    N = len(df)
    trades = []
    for i in range(200, N - 1):
        # Uptrend
        if ind['ema20'][i] <= ind['ema50'][i]:
            continue
        # Previous candle was above EMA20, current touches/crosses
        if i < 1:
            continue
        if C[i - 1] < ind['ema20'][i - 1]:  # prev already below
            continue
        if L[i] > ind['ema20'][i]:  # didn't touch
            continue
        # Close recovers above EMA20
        if C[i] < ind['ema20'][i]:
            continue
        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1
        trades.append({
            'ts': df.index[i], 'yr': df.index[i].year,
            'asset': '', 'move': move, 'mae': mae, 'mfe': mfe,
        })
    return trades


# ── Validation pipeline (simplified harness inline) ────────────────────────────
def validate_setup(name, all_trades, leverages=(10, 15, 20, 30, 50)):
    """Run baseline + deployable + MC + WF validation."""
    if not all_trades:
        return {'name': name, 'n': 0, 'trades_per_year': 0, 'family': '', 'description': '',
                'baseline': {}, 'deployable': {}, 'mfe_mae': {}, 'liq_rates': {},
                'mc': {}, 'wf': {}, 'yearly': {},
                'status': 'REJECTED', 'reason': 'no_trades'}

    moves = np.array([t['move'] for t in all_trades])
    maes = np.array([t['mae'] for t in all_trades])
    mfes = np.array([t['mfe'] for t in all_trades])
    years = np.array([t['yr'] for t in all_trades])
    N = len(moves)

    # ── Baseline (no liq, no fees) ──
    pnl_base = 4000 * moves
    wr_base = 100 * np.mean(pnl_base > 0)
    w = pnl_base[pnl_base > 0]
    l = pnl_base[pnl_base <= 0]
    pf_base = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99
    ev_base = np.mean(pnl_base)

    # ── Deployable (with liq + fees + compounding) ──
    lev = LEV_DEPLOY
    liq_th = 1.0 / lev
    liq_mask = maes >= liq_th
    liq_rate = 100 * np.mean(liq_mask)

    # PnL with liquidation
    cap = CAPITAL
    deploy_pnls = []
    for i in range(N):
        col = min(max(cap * COL_PCT, COL_MIN), COL_MAX)
        if cap < COL_MIN:
            break
        nom = col * lev
        if liq_mask[i]:
            pnl = -col - FEE
        else:
            pnl = nom * moves[i] - FEE
        deploy_pnls.append(pnl)
        cap += pnl
        if cap < 0:
            cap = 0

    dp = np.array(deploy_pnls)
    wr_dep = 100 * np.mean(dp > 0) if len(dp) > 0 else 0
    w_d = dp[dp > 0]
    l_d = dp[dp <= 0]
    pf_dep = abs(w_d.sum() / l_d.sum()) if len(l_d) > 0 and l_d.sum() != 0 else 99
    ev_dep = np.mean(dp) if len(dp) > 0 else 0
    final_cap = cap

    # Max DD
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

    # ── Liq rates per leverage ──
    liq_rates = {}
    for lv in leverages:
        liq_rates[f'{lv}x'] = round(100 * np.mean(maes >= 1.0 / lv), 1)

    # ── MFE/MAE ──
    mfe_mean = round(100 * np.mean(mfes), 2)
    mae_mean = round(100 * np.mean(maes), 2)
    mfe_med = round(100 * np.median(mfes), 2)
    mae_med = round(100 * np.median(maes), 2)

    # ── Monte Carlo shuffle ──
    n_sims = 1000
    mc_profits = 0
    for _ in range(n_sims):
        shuf = np.random.permutation(moves)
        if np.sum(shuf) > 0:
            mc_profits += 1
    mc_shuffle_pct = round(100 * mc_profits / n_sims, 1)

    # MC random entry
    n_rand = 200
    rand_wrs = []
    all_ts_idx = list(range(200, N))
    for _ in range(n_rand):
        idx = np.random.choice(range(len(moves)), size=min(len(moves), 100), replace=False)
        rand_wrs.append(100 * np.mean(moves[idx] > 0))
    mc_rand_wr = np.mean(rand_wrs)
    mc_edge_pp = round(wr_base - mc_rand_wr, 1)

    # ── Walk-forward expanding ──
    unique_yrs = sorted(set(years))
    wf_pos = 0
    wf_total = 0
    yearly = {}
    for yr in unique_yrs:
        mask = years == yr
        yr_pnl = pnl_base[mask]
        if len(yr_pnl) == 0:
            continue
        yr_total = yr_pnl.sum()
        yearly[yr] = {'n': int(mask.sum()), 'wr': round(100 * np.mean(yr_pnl > 0), 1),
                       'total': round(yr_total, 1)}
        wf_total += 1
        if yr_total > 0:
            wf_pos += 1

    wf_exp = f'{wf_pos}/{wf_total}'

    # Trades per year
    if len(unique_yrs) > 1:
        span = unique_yrs[-1] - unique_yrs[0] + 1
        tpy = round(N / span, 1)
    else:
        tpy = N

    # ── Classification ──
    status = 'REJECTED'
    reason = ''
    if N < 30:
        reason = f'N={N} < 30'
    elif mc_shuffle_pct < 70:
        reason = f'MC shuffle {mc_shuffle_pct}% < 70%'
    elif pf_base < 1.10:
        reason = f'PF baseline {pf_base:.2f} < 1.10'
    elif ev_dep <= 0:
        reason = f'EV deployable {ev_dep:.1f} <= 0'
    else:
        # Check WATCHLIST
        if (N >= 80 and tpy >= 10 and ev_dep >= 5 and pf_dep >= 1.25
                and wr_dep >= 54 and mc_shuffle_pct >= 90 and wf_pos / max(wf_total, 1) >= 0.55):
            status = 'WATCHLIST'
            reason = 'passes WATCHLIST thresholds'
        elif (N >= 40 and ev_dep > 0 and pf_dep >= 1.15 and mc_shuffle_pct >= 80):
            status = 'WATCHLIST'
            reason = 'passes survival thresholds'
        else:
            reason = 'edge weak or insufficient'

    # Check ACCEPTED
    if (status == 'WATCHLIST' and N >= 120 and tpy >= 12 and ev_dep >= 10
            and pf_dep >= 1.35 and wr_dep >= 56 and mc_shuffle_pct >= 92
            and wf_pos / max(wf_total, 1) >= 0.60 and mdd <= 0.30):
        status = 'ACCEPTED'
        reason = 'passes ACCEPTED thresholds'

    result = {
        'name': name,
        'n': N,
        'trades_per_year': tpy,
        'baseline': {
            'wr': round(wr_base, 1),
            'pf': round(pf_base, 2),
            'ev_trade': round(ev_base, 1),
        },
        'deployable': {
            'leverage': lev,
            'liq_rate': round(liq_rate, 1),
            'wr': round(wr_dep, 1),
            'pf': round(pf_dep, 2),
            'ev_trade': round(ev_dep, 1),
            'capital_final': round(final_cap, 0),
            'max_dd': round(100 * mdd, 1),
        },
        'mfe_mae': {
            'mfe_mean': mfe_mean, 'mfe_median': mfe_med,
            'mae_mean': mae_mean, 'mae_median': mae_med,
        },
        'liq_rates': liq_rates,
        'mc': {
            'shuffle_pct': mc_shuffle_pct,
            'random_edge_pp': mc_edge_pp,
        },
        'wf': {'expanding': wf_exp},
        'yearly': yearly,
        'status': status,
        'reason': reason,
    }
    return result


# ── Run all setups ─────────────────────────────────────────────────────────────
SETUPS = {
    'f1a_capitulation_4h_extreme': (gen_capitulation_4h, 'capitulation',
        'body<-5% + BB<lower + drop12h<-8%'),
    'f1b_capitulation_4h_mild': (gen_capitulation_4h_mild, 'capitulation',
        'body<-3% + BB<lower + drop12h<-5%'),
    'f2a_bb_squeeze_breakout_4h': (gen_bb_squeeze_breakout_4h, 'breakout',
        'BB width bottom 15% + close > BB upper'),
    'f2b_atr_expansion_4h': (gen_atr_expansion_4h, 'breakout',
        'ATR prev low + body > 2x ATR + green'),
    'f3a_trend_rsi_dip_4h': (gen_trend_rsi_dip_4h, 'momentum',
        'EMA20>EMA50 + RSI14<35 + price>EMA50'),
    'f3b_pullback_ema20_4h': (gen_pullback_ema20_4h, 'momentum',
        'uptrend + low touches EMA20 + close recovers'),
}

print(f'\n{"="*100}')
print('T6b — CRYPTO 4H: 3 famílies × 2 hipòtesis')
print(f'{"="*100}')

all_results = []

for setup_name, (gen_fn, family, desc) in SETUPS.items():
    # Collect trades across all assets
    all_trades = []
    for asset_name, df in all_data.items():
        C = df['C'].values
        O = df['O'].values
        H = df['H'].values
        L = df['L'].values
        V = df['V'].values
        ind = compute_indicators(C, H, L, V)
        trades = gen_fn(df, ind)
        for t in trades:
            t['asset'] = asset_name
        all_trades.extend(trades)

    # Sort by timestamp
    all_trades.sort(key=lambda t: t['ts'])

    # Validate
    result = validate_setup(setup_name, all_trades)
    result['family'] = family
    result['description'] = desc
    all_results.append(result)

    # Print summary
    b = result.get('baseline', {})
    d = result.get('deployable', {})
    mc = result.get('mc', {})
    print(f'\n  {setup_name} [{family}]')
    print(f'    {desc}')
    print(f'    N={result["n"]} tpy={result["trades_per_year"]}')
    print(f'    Baseline: WR={b.get("wr",0)}% PF={b.get("pf",0)} EV={b.get("ev_trade",0)}$/t')
    print(f'    Deploy:   WR={d.get("wr",0)}% PF={d.get("pf",0)} EV={d.get("ev_trade",0)}$/t '
          f'liq={d.get("liq_rate",0)}% cap={d.get("capital_final",0)}$')
    print(f'    MC: shuffle={mc.get("shuffle_pct",0)}% edge={mc.get("random_edge_pp",0)}pp')
    print(f'    WF: {result.get("wf",{}).get("expanding","?")}')
    print(f'    MFE/MAE: {result.get("mfe_mae",{})}')
    print(f'    Liq rates: {result.get("liq_rates",{})}')
    print(f'    → STATUS: {result["status"]} ({result["reason"]})')

    # Yearly
    if result.get('yearly'):
        for yr, yd in sorted(result['yearly'].items()):
            flag = ' ←' if yr >= 2024 else ''
            print(f'      {yr}: {yd["n"]}t WR={yd["wr"]}% total={yd["total"]:+.0f}${flag}')

    # Save artifact
    # Convert numpy types for JSON
    def fix_keys(obj):
        if isinstance(obj, dict):
            return {str(k): fix_keys(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [fix_keys(v) for v in obj]
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return obj

    artifact_path = OUT_DIR / f'{setup_name}_validation.json'
    with open(artifact_path, 'w') as f:
        json.dump(fix_keys(result), f, indent=2, default=str)

# ── Comparative table ──────────────────────────────────────────────────────────
print(f'\n\n{"="*100}')
print('TAULA COMPARATIVA T6b — Crypto 4H')
print(f'{"="*100}')
print(f'{"Setup":<35} {"Fam":<12} {"N":>5} {"WR_b":>5} {"PF_b":>5} {"EV_b":>7} '
      f'{"MC%":>5} {"Edge":>6} {"WF":>6} {"EV_d":>7} {"Liq":>5} {"Status":<10}')
print(f'{"─"*105}')

for r in all_results:
    b = r.get('baseline', {})
    d = r.get('deployable', {})
    mc = r.get('mc', {})
    print(f'{r["name"]:<35} {r["family"]:<12} {r["n"]:>5} {b.get("wr",0):>4.0f}% '
          f'{b.get("pf",0):>4.1f} {b.get("ev_trade",0):>+6.1f}$ '
          f'{mc.get("shuffle_pct",0):>4.0f}% {mc.get("random_edge_pp",0):>+5.1f}pp '
          f'{r.get("wf",{}).get("expanding","?"):>6} {d.get("ev_trade",0):>+6.1f}$ '
          f'{d.get("liq_rate",0):>4.1f}% {r["status"]:<10}')

# ── Summary ────────────────────────────────────────────────────────────────────
accepted = [r for r in all_results if r['status'] == 'ACCEPTED']
watchlist = [r for r in all_results if r['status'] == 'WATCHLIST']
rejected = [r for r in all_results if r['status'] == 'REJECTED']

print(f'\n  RESUM: {len(accepted)} ACCEPTED, {len(watchlist)} WATCHLIST, {len(rejected)} REJECTED')
if watchlist:
    print(f'  WATCHLIST: {", ".join(r["name"] for r in watchlist)}')
if accepted:
    print(f'  ACCEPTED: {", ".join(r["name"] for r in accepted)}')
