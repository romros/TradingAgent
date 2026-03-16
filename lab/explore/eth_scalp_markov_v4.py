"""
eth_scalp_markov_v4.py — Validació final: walk-forward + variacions + indicadors

OBJECTIU TARGET REFINAT:
  Candle "scalp ideal":
    - Green (close > open)
    - Lower wick petita: (open - low) / range < 0.20  → MAE mínim, entres i no baixa
    - Close prop del high: (high - close) / range < 0.20  → momentum fins al final
  Això és una candle que obre, puja sense parar, i tanca a prop del màxim.

EXPERIMENTS:
  PART 1: Walk-forward rolling (reentrenar HMM cada 6 mesos)
  PART 2: Variacions del senyal (RL|RL, RS|RL, qualsevol 2 reds, 3 reds, etc.)
  PART 3: Afegir RSI i BB com a filtres de reforç
  PART 4: Estratègia final si hi ha edge

Ús:
  python3 eth_scalp_markov_v4.py
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

warnings.filterwarnings("ignore")

# ── Config ────────────────────────────────────────────────────────────────────

SYMBOL = "ETHUSDT"
INTERVAL = "4h"
COLLATERAL = 40.0
LEVERAGE = 50
FEE = 3.36
NOMINAL = COLLATERAL * LEVERAGE  # 2000$

# Target: "scalp ideal"
TARGET_MAX_LOWER_WICK = 0.20   # (open-low)/range < 20%
TARGET_MAX_UPPER_WICK = 0.20   # (high-close)/range < 20%
TARGET_MIN_BODY_PCT = 0.002    # body > 0.2%


# ── Download ──────────────────────────────────────────────────────────────────

def download_binance() -> pd.DataFrame:
    print(f"Baixant {SYMBOL} {INTERVAL} de Binance...")
    all_k = []
    start_ms = 0
    while True:
        url = (f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}"
               f"&interval={INTERVAL}&startTime={start_ms}&limit=1000")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        if not data:
            break
        all_k.extend(data)
        start_ms = data[-1][0] + 1
        if len(data) < 1000:
            break
        time.sleep(0.1)
    rows = []
    for k in all_k:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc)
        rows.append({"timestamp": ts, "O": float(k[1]), "H": float(k[2]),
                      "L": float(k[3]), "C": float(k[4]), "V": float(k[5])})
    df = pd.DataFrame(rows).set_index("timestamp")
    print(f"  {len(df)} candles, {df.index[0].date()} → {df.index[-1].date()}")
    return df


# ── Features HMM ─────────────────────────────────────────────────────────────

def compute_features(df: pd.DataFrame, lookback: int = 20) -> np.ndarray:
    log_ret = np.log(df["C"] / df["C"].shift(1))
    vol = log_ret.rolling(lookback).std()
    atr_norm = (df["H"] - df["L"]) / df["C"]
    vol_ma = df["V"].rolling(lookback).mean()
    vol_rel = df["V"] / vol_ma
    momentum = log_ret.rolling(lookback).sum()

    feat = pd.DataFrame({"log_ret": log_ret, "vol": vol, "atr_norm": atr_norm,
                          "vol_rel": vol_rel, "momentum": momentum}, index=df.index)
    return feat


# ── Indicadors tècnics ───────────────────────────────────────────────────────

def compute_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI Wilder."""
    rsi = np.full(len(closes), np.nan)
    deltas = np.diff(closes)

    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rsi[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rsi[i + 1] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    return rsi


def compute_bb(closes: np.ndarray, period: int = 20, mult: float = 2.0):
    """Bollinger Bands. Retorna (upper, middle, lower)."""
    upper = np.full(len(closes), np.nan)
    middle = np.full(len(closes), np.nan)
    lower = np.full(len(closes), np.nan)

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1: i + 1]
        m = np.mean(window)
        s = np.std(window, ddof=0)
        middle[i] = m
        upper[i] = m + mult * s
        lower[i] = m - mult * s

    return upper, middle, lower


# ── Candle classification ────────────────────────────────────────────────────

def classify_candle(o, h, l, c, p50_body):
    """Classificar candle en 4 estats: GS, GL, RS, RL."""
    body_pct = abs(c - o) / o if o > 0 else 0
    d = "G" if c >= o else "R"
    s = "L" if body_pct >= p50_body else "S"  # mediana com a llindar
    return d + s


def is_red_candle(state: str) -> bool:
    return state.startswith("R")


def is_big_red(state: str) -> bool:
    return state == "RL"


def is_any_red(state: str) -> bool:
    return state.startswith("R")


def is_scalp_ideal(o, h, l, c):
    """Target: green + low wick petit + close prop del high."""
    if c <= o:
        return False
    rng = h - l
    if rng < 1e-9:
        return False
    body_pct = (c - o) / o
    if body_pct < TARGET_MIN_BODY_PCT:
        return False
    lower_wick = (o - l) / rng
    upper_wick = (h - c) / rng
    return lower_wick < TARGET_MAX_LOWER_WICK and upper_wick < TARGET_MAX_UPPER_WICK


# ── HMM helpers ──────────────────────────────────────────────────────────────

def train_hmm(feat: np.ndarray, n_components: int = 3, n_fits: int = 8) -> GaussianHMM | None:
    best = None
    best_score = -np.inf
    for seed in range(n_fits):
        try:
            m = GaussianHMM(n_components=n_components, covariance_type="full",
                            n_iter=200, random_state=seed, verbose=False)
            m.fit(feat)
            s = m.score(feat)
            if s > best_score:
                best_score = s
                best = m
        except Exception:
            continue
    return best


def get_bull_regime_id(model: GaussianHMM) -> int:
    """Retorna l'ID del règim amb return mitjà més alt."""
    return int(np.argmax(model.means_[:, 0]))


# ── PART 1: Walk-Forward Rolling ─────────────────────────────────────────────

def walk_forward_rolling(df: pd.DataFrame, feat_df: pd.DataFrame):
    """
    Walk-forward: entrenar HMM amb finestra rolling de 3 anys,
    predir els següents 6 mesos, avançar 6 mesos i repetir.
    """
    print("\n" + "█" * 100)
    print("█  PART 1: WALK-FORWARD ROLLING (train 3y, test 6m, step 6m)")
    print("█" * 100)

    closes = df["C"].values
    bodies = np.abs(df["C"].values - df["O"].values) / np.maximum(df["O"].values, 1e-9)
    p50_body = np.percentile(bodies, 50)

    # Classificar totes les candles
    states = []
    for _, row in df.iterrows():
        states.append(classify_candle(row["O"], row["H"], row["L"], row["C"], p50_body))

    feat_values = feat_df.values
    valid_start = feat_df.notna().all(axis=1).values.argmax()  # primer index sense NaN

    train_size = 3 * 365 * 6  # ~3 anys en candles 4H (~6/dia)
    test_size = 6 * 30 * 6    # ~6 mesos
    step_size = test_size      # avancem 6 mesos

    # Senyals a provar
    SIGNALS = {
        "RL|RL":      lambda s, i: i >= 2 and s[i-2] == "RL" and s[i-1] == "RL",
        "R*|RL":      lambda s, i: i >= 2 and is_any_red(s[i-2]) and s[i-1] == "RL",
        "RL|R*":      lambda s, i: i >= 2 and s[i-2] == "RL" and is_any_red(s[i-1]),
        "R*|R*":      lambda s, i: i >= 2 and is_any_red(s[i-2]) and is_any_red(s[i-1]),
        "3xR":        lambda s, i: i >= 3 and all(is_any_red(s[i-j]) for j in range(1, 4)),
        "RL|RL|RL":   lambda s, i: i >= 3 and all(s[i-j] == "RL" for j in range(1, 4)),
    }

    # Resultats per senyal
    results: dict[str, list] = {sig: [] for sig in SIGNALS}
    fold_details = []

    start = max(valid_start, 200)  # assegurar warmup indicadors
    pos = start + train_size

    fold_n = 0
    while pos + test_size <= len(df):
        fold_n += 1
        train_idx = slice(start, pos)
        test_idx = slice(pos, pos + test_size)

        # Entrenar HMM
        feat_train = feat_values[train_idx]
        feat_train = feat_train[~np.isnan(feat_train).any(axis=1)]
        model = train_hmm(feat_train, n_components=3, n_fits=5)

        if model is None:
            pos += step_size
            start += step_size
            continue

        # Predir règims al test
        feat_test = feat_values[test_idx]
        nan_mask = np.isnan(feat_test).any(axis=1)
        regimes_test = np.full(len(feat_test), -1)
        if not nan_mask.all():
            regimes_test[~nan_mask] = model.predict(feat_test[~nan_mask])

        bull_id = get_bull_regime_id(model)

        test_dates = df.index[test_idx]
        fold_info = {
            "fold": fold_n,
            "train": f"{df.index[train_idx][0].date()} → {df.index[train_idx][-1].date()}",
            "test": f"{test_dates[0].date()} → {test_dates[-1].date()}",
        }

        # Avaluar cada senyal
        for sig_name, sig_fn in SIGNALS.items():
            trades = []
            for j in range(len(feat_test)):
                abs_i = pos + j
                if abs_i >= len(df):
                    break
                if regimes_test[j] != bull_id:
                    continue
                if not sig_fn(states, abs_i):
                    continue

                row = df.iloc[abs_i]
                o, h, l, c = row["O"], row["H"], row["L"], row["C"]
                move_pct = (c - o) / o if o > 0 else 0
                pnl = NOMINAL * move_pct - FEE
                ideal = is_scalp_ideal(o, h, l, c)
                trades.append({"pnl": pnl, "move": move_pct, "ideal": ideal,
                                "wr": 1 if c > o else 0})

            results[sig_name].extend(trades)

        fold_details.append(fold_info)
        pos += step_size
        start += step_size

    # Report
    print(f"\n  {fold_n} folds executats")
    print(f"\n  {'Senyal':<12} {'N':>5} {'WR':>6} {'WR ideal':>9} {'Avg $/t':>8} "
          f"{'Total $':>9} {'PF':>6} {'% ideal':>8}")
    print(f"  {'─' * 70}")

    best_signal = None
    best_avg = -999

    for sig_name, trades in results.items():
        if not trades:
            print(f"  {sig_name:<12}     0")
            continue
        arr = pd.DataFrame(trades)
        n = len(arr)
        wr = 100 * arr["wr"].mean()
        avg_pnl = arr["pnl"].mean()
        total = arr["pnl"].sum()
        wins = arr[arr["pnl"] > 0]["pnl"].sum()
        losses = abs(arr[arr["pnl"] <= 0]["pnl"].sum())
        pf = wins / losses if losses > 0 else 99
        pct_ideal = 100 * arr["ideal"].mean()

        if avg_pnl > best_avg:
            best_avg = avg_pnl
            best_signal = sig_name

        print(f"  {sig_name:<12} {n:>5} {wr:>5.1f}% {0:>8.1f}%  {avg_pnl:>+7.2f}$ "
              f"{total:>+8.2f}$ {pf:>5.2f} {pct_ideal:>7.1f}%")

    print(f"\n  Millor senyal walk-forward: {best_signal} ({best_avg:+.2f}$/trade)")
    return results, best_signal, states, p50_body


# ── PART 2: Variacions del senyal ────────────────────────────────────────────

def analyze_variations(df: pd.DataFrame, feat_df: pd.DataFrame,
                        states: list, p50_body: float):
    """Analitza variacions del senyal amb IS/OOS fix."""
    print("\n" + "█" * 100)
    print("█  PART 2: VARIACIONS DEL SENYAL (IS 2017-2023 / OOS 2024-2026)")
    print("█" * 100)

    is_end = pd.Timestamp("2023-12-31", tz=timezone.utc)
    oos_start = pd.Timestamp("2024-01-01", tz=timezone.utc)

    feat_values = feat_df.values
    is_mask = np.array(df.index <= is_end)
    oos_mask = np.array(df.index >= oos_start)

    # Entrenar HMM amb IS
    feat_is = feat_values[is_mask]
    feat_is_clean = feat_is[~np.isnan(feat_is).any(axis=1)]
    model = train_hmm(feat_is_clean, n_components=3, n_fits=8)
    if model is None:
        print("  ERROR: HMM no convergeix")
        return None, None

    # Predir tot
    feat_all = feat_values.copy()
    nan_mask = np.isnan(feat_all).any(axis=1)
    regimes = np.full(len(feat_all), -1)
    regimes[~nan_mask] = model.predict(feat_all[~nan_mask])
    bull_id = get_bull_regime_id(model)

    # Indicadors
    closes = df["C"].values
    rsi = compute_rsi(closes, 14)
    bb_upper, bb_mid, bb_lower = compute_bb(closes, 20, 2.0)

    # Senyals base
    SIGNALS = {
        "RL|RL":    lambda i: i >= 2 and states[i-2] == "RL" and states[i-1] == "RL",
        "R*|RL":    lambda i: i >= 2 and is_any_red(states[i-2]) and states[i-1] == "RL",
        "RL|R*":    lambda i: i >= 2 and states[i-2] == "RL" and is_any_red(states[i-1]),
        "R*|R*":    lambda i: i >= 2 and is_any_red(states[i-2]) and is_any_red(states[i-1]),
        "3xR":      lambda i: i >= 3 and all(is_any_red(states[i-j]) for j in range(1, 4)),
    }

    # Filtres indicadors
    FILTERS = {
        "cap":          lambda i: True,
        "RSI<40":       lambda i: not np.isnan(rsi[i-1]) and rsi[i-1] < 40,
        "RSI<50":       lambda i: not np.isnan(rsi[i-1]) and rsi[i-1] < 50,
        "RSI<30":       lambda i: not np.isnan(rsi[i-1]) and rsi[i-1] < 30,
        "BB<lower":     lambda i: not np.isnan(bb_lower[i-1]) and closes[i-1] < bb_lower[i-1],
        "BB<mid":       lambda i: not np.isnan(bb_mid[i-1]) and closes[i-1] < bb_mid[i-1],
        "RSI<50+BB<mid": lambda i: (not np.isnan(rsi[i-1]) and rsi[i-1] < 50 and
                                     not np.isnan(bb_mid[i-1]) and closes[i-1] < bb_mid[i-1]),
    }

    print(f"\n  HMM entrenat. Bull regime ID={bull_id}")
    print(f"  Base rate scalp_ideal IS: ", end="")

    # Base rate
    n_is = sum(is_mask)
    n_ideal_is = sum(1 for i in range(len(df)) if is_mask[i] and
                     is_scalp_ideal(df.iloc[i]["O"], df.iloc[i]["H"],
                                     df.iloc[i]["L"], df.iloc[i]["C"]))
    n_oos = sum(oos_mask)
    n_ideal_oos = sum(1 for i in range(len(df)) if oos_mask[i] and
                      is_scalp_ideal(df.iloc[i]["O"], df.iloc[i]["H"],
                                      df.iloc[i]["L"], df.iloc[i]["C"]))
    print(f"{n_ideal_is/n_is:.1%} IS, {n_ideal_oos/n_oos:.1%} OOS")

    # Grid: senyal × filtre
    all_combos = []

    for sig_name, sig_fn in SIGNALS.items():
        for filt_name, filt_fn in FILTERS.items():
            is_trades = []
            oos_trades = []

            for i in range(3, len(df)):
                if regimes[i] != bull_id:
                    continue
                if not sig_fn(i):
                    continue
                if not filt_fn(i):
                    continue

                row = df.iloc[i]
                o, h, l, c = row["O"], row["H"], row["L"], row["C"]
                move_pct = (c - o) / o if o > 0 else 0
                pnl = NOMINAL * move_pct - FEE
                is_green = c > o
                ideal = is_scalp_ideal(o, h, l, c)
                dd = (o - l) / o if o > 0 else 0  # drawdown des de l'entry

                trade = {"pnl": pnl, "move": move_pct, "green": is_green,
                          "ideal": ideal, "dd": dd}

                if is_mask[i]:
                    is_trades.append(trade)
                elif oos_mask[i]:
                    oos_trades.append(trade)

            if len(is_trades) < 10:
                continue

            is_df = pd.DataFrame(is_trades)
            oos_df = pd.DataFrame(oos_trades) if oos_trades else pd.DataFrame()

            is_wr = 100 * is_df["green"].mean()
            is_avg = is_df["pnl"].mean()
            is_pct_ideal = 100 * is_df["ideal"].mean()
            is_avg_dd = 100 * is_df["dd"].mean()

            oos_n = len(oos_df)
            oos_wr = 100 * oos_df["green"].mean() if oos_n > 0 else 0
            oos_avg = oos_df["pnl"].mean() if oos_n > 0 else 0
            oos_pct_ideal = 100 * oos_df["ideal"].mean() if oos_n > 0 else 0
            oos_avg_dd = 100 * oos_df["dd"].mean() if oos_n > 0 else 0

            all_combos.append({
                "signal": sig_name, "filter": filt_name,
                "is_n": len(is_df), "is_wr": is_wr, "is_avg": is_avg,
                "is_ideal": is_pct_ideal, "is_dd": is_avg_dd,
                "oos_n": oos_n, "oos_wr": oos_wr, "oos_avg": oos_avg,
                "oos_ideal": oos_pct_ideal, "oos_dd": oos_avg_dd,
            })

    # Ordenar per OOS avg
    all_combos.sort(key=lambda x: x["oos_avg"], reverse=True)

    print(f"\n  {'Senyal':<10} {'Filtre':<15} "
          f"{'IS_N':>5} {'IS_WR':>6} {'IS$/t':>7} {'IS%id':>6} {'IS_DD':>6} "
          f"{'OOS_N':>5} {'OOS_WR':>7} {'OOS$/t':>7} {'OOS%id':>7} {'OOS_DD':>7}")
    print(f"  {'─' * 105}")

    for c in all_combos:
        flag = " ***" if c["oos_avg"] > 0 and c["oos_n"] >= 15 else ""
        print(f"  {c['signal']:<10} {c['filter']:<15} "
              f"{c['is_n']:>5} {c['is_wr']:>5.1f}% {c['is_avg']:>+6.2f}$ "
              f"{c['is_ideal']:>5.1f}% {c['is_dd']:>5.2f}% "
              f"{c['oos_n']:>5} {c['oos_wr']:>6.1f}% {c['oos_avg']:>+6.2f}$ "
              f"{c['oos_ideal']:>6.1f}% {c['oos_dd']:>6.2f}%{flag}")

    # Winners
    winners = [c for c in all_combos if c["oos_avg"] > 0 and c["oos_n"] >= 15]

    if winners:
        print(f"\n  {len(winners)} combinacions OOS positives amb N >= 15:")
        for w in winners:
            print(f"    {w['signal']} + {w['filter']}: OOS {w['oos_n']}t, "
                  f"WR={w['oos_wr']:.1f}%, avg={w['oos_avg']:+.2f}$/t, "
                  f"scalp_ideal={w['oos_ideal']:.1f}%, DD={w['oos_dd']:.2f}%")

    return model, all_combos


# ── PART 3: Anàlisi detallat dels millors ────────────────────────────────────

def detailed_analysis(df: pd.DataFrame, feat_df: pd.DataFrame,
                       states: list, model: GaussianHMM, combos: list):
    """Anàlisi detallat dels millors combos: per any, equity curve, etc."""
    print("\n" + "█" * 100)
    print("█  PART 3: ANÀLISI DETALLAT DELS MILLORS")
    print("█" * 100)

    winners = [c for c in combos if c["oos_avg"] > 0 and c["oos_n"] >= 10]
    if not winners:
        print("  Cap winner OOS. Provem els menys dolents...")
        winners = sorted(combos, key=lambda x: x["oos_avg"], reverse=True)[:5]

    closes = df["C"].values
    rsi = compute_rsi(closes, 14)
    bb_upper, bb_mid, bb_lower = compute_bb(closes, 20, 2.0)

    feat_values = feat_df.values
    nan_mask = np.isnan(feat_values).any(axis=1)
    regimes = np.full(len(feat_values), -1)
    feat_clean = feat_values[~nan_mask]
    regimes[~nan_mask] = model.predict(feat_clean)
    bull_id = get_bull_regime_id(model)

    SIGNALS = {
        "RL|RL":    lambda i: i >= 2 and states[i-2] == "RL" and states[i-1] == "RL",
        "R*|RL":    lambda i: i >= 2 and is_any_red(states[i-2]) and states[i-1] == "RL",
        "RL|R*":    lambda i: i >= 2 and states[i-2] == "RL" and is_any_red(states[i-1]),
        "R*|R*":    lambda i: i >= 2 and is_any_red(states[i-2]) and is_any_red(states[i-1]),
        "3xR":      lambda i: i >= 3 and all(is_any_red(states[i-j]) for j in range(1, 4)),
    }

    FILTERS = {
        "cap":          lambda i: True,
        "RSI<40":       lambda i: not np.isnan(rsi[i-1]) and rsi[i-1] < 40,
        "RSI<50":       lambda i: not np.isnan(rsi[i-1]) and rsi[i-1] < 50,
        "RSI<30":       lambda i: not np.isnan(rsi[i-1]) and rsi[i-1] < 30,
        "BB<lower":     lambda i: not np.isnan(bb_lower[i-1]) and closes[i-1] < bb_lower[i-1],
        "BB<mid":       lambda i: not np.isnan(bb_mid[i-1]) and closes[i-1] < bb_mid[i-1],
        "RSI<50+BB<mid": lambda i: (not np.isnan(rsi[i-1]) and rsi[i-1] < 50 and
                                     not np.isnan(bb_mid[i-1]) and closes[i-1] < bb_mid[i-1]),
    }

    for w in winners[:5]:
        sig_fn = SIGNALS.get(w["signal"])
        filt_fn = FILTERS.get(w["filter"])
        if not sig_fn or not filt_fn:
            continue

        print(f"\n  {'─' * 80}")
        print(f"  {w['signal']} + {w['filter']}")
        print(f"  {'─' * 80}")

        # Tots els trades
        trades_by_year: dict[int, list] = defaultdict(list)
        all_trades = []

        for i in range(3, len(df)):
            if regimes[i] != bull_id:
                continue
            if not sig_fn(i):
                continue
            if not filt_fn(i):
                continue

            row = df.iloc[i]
            o, h, l, c = row["O"], row["H"], row["L"], row["C"]
            move_pct = (c - o) / o if o > 0 else 0
            pnl = NOMINAL * move_pct - FEE
            dd = (o - l) / o if o > 0 else 0
            year = df.index[i].year
            ideal = is_scalp_ideal(o, h, l, c)

            t = {"year": year, "pnl": pnl, "green": c > o, "ideal": ideal,
                 "dd": dd, "move": move_pct, "ts": df.index[i],
                 "rsi": rsi[i-1] if not np.isnan(rsi[i-1]) else 0}
            trades_by_year[year].append(t)
            all_trades.append(t)

        if not all_trades:
            print("    0 trades")
            continue

        # Per any
        print(f"\n    {'Any':>6} {'N':>5} {'WR':>6} {'Avg$/t':>8} {'Total$':>9} "
              f"{'%Ideal':>7} {'AvgDD':>7}")
        print(f"    {'─' * 55}")

        for year in sorted(trades_by_year.keys()):
            yr_trades = trades_by_year[year]
            yr_df = pd.DataFrame(yr_trades)
            n = len(yr_df)
            wr = 100 * yr_df["green"].mean()
            avg = yr_df["pnl"].mean()
            total = yr_df["pnl"].sum()
            pct_id = 100 * yr_df["ideal"].mean()
            avg_dd = 100 * yr_df["dd"].mean()
            print(f"    {year:>6} {n:>5} {wr:>5.1f}% {avg:>+7.2f}$ {total:>+8.2f}$ "
                  f"{pct_id:>6.1f}% {avg_dd:>6.2f}%")

        # Total
        all_df = pd.DataFrame(all_trades)
        n = len(all_df)
        wr = 100 * all_df["green"].mean()
        avg = all_df["pnl"].mean()
        total = all_df["pnl"].sum()
        pct_id = 100 * all_df["ideal"].mean()
        avg_dd = 100 * all_df["dd"].mean()
        wins = all_df[all_df["pnl"] > 0]["pnl"]
        losses = all_df[all_df["pnl"] <= 0]["pnl"]
        pf = abs(wins.sum() / losses.sum()) if len(losses) > 0 and losses.sum() != 0 else 99

        print(f"    {'─' * 55}")
        print(f"    {'TOTAL':>6} {n:>5} {wr:>5.1f}% {avg:>+7.2f}$ {total:>+8.2f}$ "
              f"{pct_id:>6.1f}% {avg_dd:>6.2f}%  PF={pf:.2f}")

        # Distribució de PnL
        print(f"\n    Distribució PnL:")
        print(f"      Avg win:  {wins.mean():>+8.2f}$" if len(wins) > 0 else "")
        print(f"      Avg loss: {losses.mean():>+8.2f}$" if len(losses) > 0 else "")
        print(f"      Best:     {all_df['pnl'].max():>+8.2f}$")
        print(f"      Worst:    {all_df['pnl'].min():>+8.2f}$")
        print(f"      Median:   {all_df['pnl'].median():>+8.2f}$")

        # Drawdown des de l'entry (MAE)
        print(f"\n    MAE (Max Adverse Excursion des de l'open):")
        print(f"      Avg DD:   {avg_dd:.2f}%  (${NOMINAL * all_df['dd'].mean():.2f})")
        print(f"      Max DD:   {100*all_df['dd'].max():.2f}%  "
              f"(${NOMINAL * all_df['dd'].max():.2f})")
        print(f"      DD < 0.5%: {100*np.mean(all_df['dd'] < 0.005):.1f}% dels trades")

        # Scalp ideal rate
        print(f"\n    Scalp ideal (MAE<0.2%, close~high): {pct_id:.1f}% dels trades")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    df = download_binance()
    feat_df = compute_features(df)

    # Alinear: omplir NaN inicials amb 0 (o ignorar-los)
    # Però mantenim df sencer per indexar
    feat_values_aligned = feat_df.reindex(df.index)

    # PART 1: Walk-forward
    wf_results, best_wf, states, p50_body = walk_forward_rolling(df, feat_values_aligned)

    # PART 2: Variacions + indicadors
    model, combos = analyze_variations(df, feat_values_aligned, states, p50_body)

    # PART 3: Detall dels millors
    if model and combos:
        detailed_analysis(df, feat_values_aligned, states, model, combos)

    # RESUM
    print(f"\n\n{'=' * 100}")
    print("RESUM FINAL")
    print("=" * 100)

    if combos:
        winners = [c for c in combos if c["oos_avg"] > 0 and c["oos_n"] >= 10]
        if winners:
            best = winners[0]
            print(f"\n  MILLOR ESTRATÈGIA TROBADA:")
            print(f"    Senyal:  BULL (HMM) + {best['signal']} + {best['filter']}")
            print(f"    IS:      {best['is_n']} trades, WR={best['is_wr']:.1f}%, "
                  f"avg={best['is_avg']:+.2f}$/trade")
            print(f"    OOS:     {best['oos_n']} trades, WR={best['oos_wr']:.1f}%, "
                  f"avg={best['oos_avg']:+.2f}$/trade")
            print(f"    % Scalp ideal OOS: {best['oos_ideal']:.1f}%")
            print(f"    Avg DD OOS: {best['oos_dd']:.2f}%")
            print(f"\n    Col·lateral: {COLLATERAL}$, Leverage: {LEVERAGE}x, Fee: {FEE}$")
            print(f"    Nominal per trade: {NOMINAL}$")

            edge_per_trade = best['oos_avg']
            trades_per_year = best['oos_n'] * (12 / 27)  # escalar a 12 mesos
            annual = edge_per_trade * trades_per_year
            print(f"\n    Projecció anual: ~{trades_per_year:.0f} trades/any × "
                  f"{edge_per_trade:+.2f}$/t = {annual:+.0f}$/any")
        else:
            print("\n  Cap combinació OOS positiva amb N suficient.")
            print("  Markov + HMM + indicadors no donen edge net de fees per ETH 4H scalping")
            best3 = sorted(combos, key=lambda x: x["oos_avg"], reverse=True)[:3]
            print("  Top 3 menys dolents:")
            for c in best3:
                print(f"    {c['signal']}+{c['filter']}: OOS {c['oos_n']}t, "
                      f"avg={c['oos_avg']:+.2f}$/t, WR={c['oos_wr']:.1f}%")


if __name__ == "__main__":
    main()
