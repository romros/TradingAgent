"""
eth_scalp_markov_v2.py — Iteració 2: buscar la millor combinació anti-overfitting

REFLEXIONS de v1:
  - 14 estats → trigrams amb N=15-22 → overfitting brutal (IS +15$/trade, OOS -14$/trade)
  - El base rate de "clean green" (16%) és difícil de batre amb seqüències discretes
  - Cal: menys estats, més dades per trigram, objectiu menys restrictiu

EXPERIMENTS SISTEMÀTICS:
  A) Classificació de candles: provar 3, 4, 6, 8 estats
  B) Profunditat Markov: 1-gram, 2-gram, 3-gram
  C) Objectiu: "clean green" vs "qualsevol green" vs "green + move > X%"
  D) Filtre de règim: afegir ATR o tendència EMA com a capa addicional (no com estat)
  E) Mètode de selecció: no top-N score, sinó trigrams que superen base rate amb IC 95%

MILLOR ENFOCAMENT TEÒRIC:
  - Menys estats → més N per trigram → menys variança
  - Interval de confiança per filtrar trigrams reals vs soroll
  - Validació walk-forward (no IS/OOS fix) per robustesa

Ús:
  python3 eth_scalp_markov_v2.py
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd


# ── Config ────────────────────────────────────────────────────────────────────

SYMBOL = "ETHUSDT"
INTERVAL = "4h"

COLLATERAL = 40.0
LEVERAGE = 50
FEE = 3.36
NOMINAL = COLLATERAL * LEVERAGE  # 2000$

# Walk-forward: 3 folds
FOLDS = [
    ("F1 IS", "F1 OOS", "2017-08-17", "2020-12-31", "2021-01-01", "2022-06-30"),
    ("F2 IS", "F2 OOS", "2018-01-01", "2022-06-30", "2022-07-01", "2024-06-30"),
    ("F3 IS", "F3 OOS", "2019-01-01", "2024-06-30", "2024-07-01", "2026-03-15"),
]


# ── Binance download (reutilitzem de v1) ─────────────────────────────────────

def download_binance(symbol: str = SYMBOL, interval: str = INTERVAL) -> pd.DataFrame:
    print(f"Baixant {symbol} {interval} de Binance...")
    all_k = []
    start_ms = 0
    url_base = "https://api.binance.com/api/v3/klines"
    while True:
        url = f"{url_base}?symbol={symbol}&interval={interval}&startTime={start_ms}&limit=1000"
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


# ── Classificadors de candles ────────────────────────────────────────────────

def classify_2state(o, h, l, c, body_pct, lw, uw, p33, p66):
    """2 estats: G / R"""
    return "G" if c >= o else "R"

def classify_4state(o, h, l, c, body_pct, lw, uw, p33, p66):
    """4 estats: GS, GL, RS, RL (small vs large body)"""
    d = "G" if c >= o else "R"
    s = "S" if body_pct < p66 else "L"  # 2/3 small, 1/3 large
    return d + s

def classify_4state_v2(o, h, l, c, body_pct, lw, uw, p33, p66):
    """4 estats: momentum-based: UP, up, dn, DN"""
    if c >= o:
        return "UP" if body_pct >= p66 else "up"
    else:
        return "DN" if body_pct >= p66 else "dn"

def classify_6state(o, h, l, c, body_pct, lw, uw, p33, p66):
    """6 estats: G/R × S/M/L"""
    d = "G" if c >= o else "R"
    if body_pct < p33:
        s = "S"
    elif body_pct < p66:
        s = "M"
    else:
        s = "L"
    return d + s

def classify_6state_wick(o, h, l, c, body_pct, lw, uw, p33, p66):
    """6 estats: G/R × normal/hammer/star (centrat en wicks, no body size)"""
    d = "G" if c >= o else "R"
    if lw > 0.45:
        w = "h"   # hammer: rebuig de mínims
    elif uw > 0.45:
        w = "s"   # shooting star: rebuig de màxims
    else:
        w = "n"   # normal
    return d + w

def classify_8state(o, h, l, c, body_pct, lw, uw, p33, p66):
    """8 estats: G/R × S/L × hammer_or_not"""
    d = "G" if c >= o else "R"
    s = "S" if body_pct < p66 else "L"
    w = "h" if lw > 0.40 else ""
    return d + s + w


CLASSIFIERS = {
    "2st": classify_2state,
    "4st": classify_4state,
    "4v2": classify_4state_v2,
    "6st": classify_6state,
    "6wk": classify_6state_wick,
    "8st": classify_8state,
}


# ── Preparar candles amb tots els classificadors ─────────────────────────────

@dataclass
class Candle:
    ts: pd.Timestamp
    o: float; h: float; l: float; c: float
    body_pct: float
    lw: float  # lower wick ratio
    uw: float  # upper wick ratio
    states: dict  # classifier_name → state string
    is_green: bool
    move_pct: float  # (c-o)/o


def prepare_candles(df: pd.DataFrame) -> list[Candle]:
    candles = []
    for ts, row in df.iterrows():
        o, h, l, c = row["O"], row["H"], row["L"], row["C"]
        rng = h - l
        if rng < 1e-9:
            continue
        body_pct = abs(c - o) / o
        bt = max(o, c)
        bb = min(o, c)
        lw = (bb - l) / rng
        uw = (h - bt) / rng
        candles.append(Candle(
            ts=ts, o=o, h=h, l=l, c=c,
            body_pct=body_pct, lw=lw, uw=uw,
            states={}, is_green=c >= o,
            move_pct=(c - o) / o,
        ))

    # Percentils per classificadors que els necessiten
    bodies = np.array([c.body_pct for c in candles])
    p33 = np.percentile(bodies, 33.3)
    p66 = np.percentile(bodies, 66.6)

    for c in candles:
        for name, func in CLASSIFIERS.items():
            c.states[name] = func(c.o, c.h, c.l, c.c, c.body_pct, c.lw, c.uw, p33, p66)

    return candles


# ── Objectius (target) ───────────────────────────────────────────────────────

def target_any_green(c: Candle) -> bool:
    """Qualsevol candle verda."""
    return c.is_green

def target_clean_green(c: Candle) -> bool:
    """Green + lower wick < 15% + body > 0.3%."""
    return c.is_green and c.lw < 0.15 and c.body_pct >= 0.003

def target_strong_green(c: Candle) -> bool:
    """Green + move > 0.5%."""
    return c.is_green and c.move_pct > 0.005

def target_green_low_dd(c: Candle) -> bool:
    """Green + drawdown < 0.3% (low no baixa gaire de l'open)."""
    dd = (c.o - c.l) / c.o if c.o > 0 else 0
    return c.is_green and dd < 0.003


TARGETS = {
    "any_green":    target_any_green,
    "clean_green":  target_clean_green,
    "strong_green": target_strong_green,
    "green_low_dd": target_green_low_dd,
}


# ── Interval de confiança Wilson ─────────────────────────────────────────────

def wilson_lower(n_success: int, n_total: int, z: float = 1.96) -> float:
    """Límit inferior de l'IC Wilson al 95%. Més conservador que p_hat per N petits."""
    if n_total == 0:
        return 0.0
    p = n_success / n_total
    denom = 1 + z * z / n_total
    center = p + z * z / (2 * n_total)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n_total)) / n_total)
    return (center - spread) / denom


# ── Experiment complet ───────────────────────────────────────────────────────

@dataclass
class ExperimentResult:
    classifier: str
    depth: int  # 1=unigram, 2=bigram, 3=trigram
    target: str
    n_states: int
    n_possible_grams: int
    n_grams_with_data: int
    n_grams_significant: int  # Wilson lower > base_rate
    base_rate_is: float
    base_rate_oos: float
    # Simulació amb grams significatius
    is_trades: int; is_wr: float; is_avg: float; is_pf: float
    oos_trades: int; oos_wr: float; oos_avg: float; oos_pf: float
    # Detall grams significatius
    top_grams: list  # [(gram, n_is, p_is, n_oos, p_oos)]


def run_experiment(candles: list[Candle], classifier: str, depth: int,
                   target_name: str, is_end: pd.Timestamp,
                   oos_start: pd.Timestamp, min_n: int = 30) -> ExperimentResult:
    """Executa un experiment: classifier × depth × target."""

    target_fn = TARGETS[target_name]
    c_is = [c for c in candles if c.ts <= is_end]
    c_oos = [c for c in candles if c.ts >= oos_start]

    # Base rates
    br_is = sum(1 for c in c_is if target_fn(c)) / len(c_is) if c_is else 0
    br_oos = sum(1 for c in c_oos if target_fn(c)) / len(c_oos) if c_oos else 0

    # Construir n-grams IS
    def get_gram(candles_list, idx):
        parts = []
        for d in range(depth, 0, -1):
            parts.append(candles_list[idx - d].states[classifier])
        return "|".join(parts)

    # IS: comptar targets per gram
    gram_hits_is: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    is_data: dict[str, list] = defaultdict(list)
    for i in range(depth, len(c_is)):
        gram = get_gram(c_is, i)
        hit = target_fn(c_is[i])
        old = gram_hits_is[gram]
        gram_hits_is[gram] = (old[0] + (1 if hit else 0), old[1] + 1)
        is_data[gram].append(c_is[i])

    # OOS: comptar
    gram_hits_oos: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    oos_data: dict[str, list] = defaultdict(list)
    for i in range(depth, len(c_oos)):
        gram = get_gram(c_oos, i)
        hit = target_fn(c_oos[i])
        old = gram_hits_oos[gram]
        gram_hits_oos[gram] = (old[0] + (1 if hit else 0), old[1] + 1)
        oos_data[gram].append(c_oos[i])

    # Comptar estats únics
    unique_states = set(c.states[classifier] for c in candles)
    n_states = len(unique_states)
    n_possible = n_states ** depth

    # Seleccionar grams significatius: Wilson lower > base_rate IS + mínim N
    significant_grams = []
    for gram, (hits, total) in gram_hits_is.items():
        if total < min_n:
            continue
        wl = wilson_lower(hits, total)
        p_hat = hits / total
        if wl > br_is:  # significativament per sobre del base rate
            # Buscar OOS
            oos_hits, oos_total = gram_hits_oos.get(gram, (0, 0))
            oos_p = oos_hits / oos_total if oos_total > 0 else 0
            significant_grams.append((gram, total, p_hat, wl, oos_total, oos_p))

    significant_grams.sort(key=lambda x: x[3], reverse=True)  # per Wilson lower

    # Simulació amb grams significatius
    sig_set = {g[0] for g in significant_grams}

    def simulate(candle_list):
        trades_pnl = []
        for i in range(depth, len(candle_list)):
            gram = get_gram(candle_list, i)
            if gram not in sig_set:
                continue
            c = candle_list[i]
            pnl = NOMINAL * c.move_pct - FEE
            trades_pnl.append(pnl)
        if not trades_pnl:
            return 0, 0.0, 0.0, 0.0
        arr = np.array(trades_pnl)
        wins = arr[arr > 0]
        losses = arr[arr <= 0]
        wr = len(wins) / len(arr) * 100
        avg = arr.mean()
        pf = abs(wins.sum() / losses.sum()) if len(losses) > 0 and losses.sum() != 0 else 99.0
        return len(arr), wr, avg, pf

    is_n, is_wr, is_avg, is_pf = simulate(c_is)
    oos_n, oos_wr, oos_avg, oos_pf = simulate(c_oos)

    top_detail = [(g[0], g[1], g[2], g[4], g[5]) for g in significant_grams[:10]]

    return ExperimentResult(
        classifier=classifier, depth=depth, target=target_name,
        n_states=n_states, n_possible_grams=n_possible,
        n_grams_with_data=len(gram_hits_is),
        n_grams_significant=len(significant_grams),
        base_rate_is=br_is, base_rate_oos=br_oos,
        is_trades=is_n, is_wr=is_wr, is_avg=is_avg, is_pf=is_pf,
        oos_trades=oos_n, oos_wr=oos_wr, oos_avg=oos_avg, oos_pf=oos_pf,
        top_grams=top_detail,
    )


# ── Walk-forward validation ──────────────────────────────────────────────────

def walk_forward(candles: list[Candle], classifier: str, depth: int,
                 target_name: str, min_n: int = 30) -> dict:
    """3-fold walk-forward: entrena a IS, valida a OOS de cada fold."""
    results = []
    for fold_name_is, fold_name_oos, is_from, is_to, oos_from, oos_to in FOLDS:
        is_end = pd.Timestamp(is_to, tz=timezone.utc)
        oos_start = pd.Timestamp(oos_from, tz=timezone.utc)
        oos_end = pd.Timestamp(oos_to, tz=timezone.utc)

        c_fold = [c for c in candles if c.ts <= oos_end]
        res = run_experiment(c_fold, classifier, depth, target_name, is_end, oos_start, min_n)
        results.append((fold_name_oos, res))

    # Agregar OOS
    total_oos_trades = sum(r.oos_trades for _, r in results)
    if total_oos_trades == 0:
        return {"classifier": classifier, "depth": depth, "target": target_name,
                "oos_trades": 0, "oos_wr": 0, "oos_avg": 0, "oos_pf": 0,
                "folds": results}

    total_oos_pnl = sum(r.oos_avg * r.oos_trades for _, r in results)
    avg_oos = total_oos_pnl / total_oos_trades
    # WR aproximat
    avg_wr = sum(r.oos_wr * r.oos_trades for _, r in results) / total_oos_trades

    return {"classifier": classifier, "depth": depth, "target": target_name,
            "oos_trades": total_oos_trades, "oos_wr": avg_wr, "oos_avg": avg_oos,
            "folds": results}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    df = download_binance()
    candles = prepare_candles(df)
    print(f"  {len(candles)} candles preparades\n")

    # ── PART 1: Grid complet de experiments IS/OOS fix ────────────────────────
    is_end = pd.Timestamp("2023-12-31", tz=timezone.utc)
    oos_start = pd.Timestamp("2024-01-01", tz=timezone.utc)

    print("=" * 100)
    print("PART 1: GRID SYSTEMATIC — Classifier × Depth × Target (IS→2023 / OOS 2024→)")
    print("=" * 100)

    all_results: list[ExperimentResult] = []

    for clf_name in CLASSIFIERS:
        for depth in [1, 2, 3]:
            for tgt_name in TARGETS:
                res = run_experiment(candles, clf_name, depth, tgt_name,
                                     is_end, oos_start, min_n=30)
                all_results.append(res)

    # Taula resum — ordenada per OOS avg/trade
    all_results.sort(key=lambda r: r.oos_avg, reverse=True)

    print(f"\n  {'Clf':>4} {'D':>1} {'Target':<13} {'#St':>3} {'#Sig':>4} "
          f"{'BR_IS':>6} {'IS_N':>5} {'IS_WR':>6} {'IS$/t':>7} {'IS_PF':>6} "
          f"{'OOS_N':>5} {'OOS_WR':>6} {'OOS$/t':>7} {'OOS_PF':>6}")
    print(f"  {'─' * 95}")

    for r in all_results:
        if r.n_grams_significant == 0:
            continue
        flag = " ***" if r.oos_avg > 0 and r.oos_trades >= 20 else ""
        print(f"  {r.classifier:>4} {r.depth:>1} {r.target:<13} {r.n_states:>3} "
              f"{r.n_grams_significant:>4} {r.base_rate_is:>5.1%} "
              f"{r.is_trades:>5} {r.is_wr:>5.1f}% {r.is_avg:>+6.2f}$ {r.is_pf:>5.2f} "
              f"{r.oos_trades:>5} {r.oos_wr:>5.1f}% {r.oos_avg:>+6.2f}$ {r.oos_pf:>5.2f}{flag}")

    # ── PART 2: Detall dels millors (OOS positius amb N decent) ──────────────

    winners = [r for r in all_results if r.oos_avg > 0 and r.oos_trades >= 20]
    if winners:
        print(f"\n\n{'=' * 100}")
        print(f"PART 2: DETALL DELS {len(winners)} GUANYADORS OOS")
        print("=" * 100)

        for r in winners[:10]:
            print(f"\n  {r.classifier} depth={r.depth} target={r.target}")
            print(f"  IS:  {r.is_trades} trades, WR={r.is_wr:.1f}%, avg={r.is_avg:+.2f}$, PF={r.is_pf:.2f}")
            print(f"  OOS: {r.oos_trades} trades, WR={r.oos_wr:.1f}%, avg={r.oos_avg:+.2f}$, PF={r.oos_pf:.2f}")
            print(f"  N-grams significatius (Wilson lower > base rate {r.base_rate_is:.1%}):")
            print(f"    {'Gram':<22} {'N_IS':>5} {'P_IS':>6} {'N_OOS':>6} {'P_OOS':>7} {'Δ':>6}")
            print(f"    {'─' * 50}")
            for gram, n_is, p_is, n_oos, p_oos in r.top_grams:
                delta = p_oos - p_is if n_oos > 0 else float('nan')
                d_str = f"{delta:+5.1%}" if not math.isnan(delta) else "  —"
                print(f"    {gram:<22} {n_is:>5} {p_is:>5.1%} {n_oos:>6} {p_oos:>6.1%} {d_str}")

    # ── PART 3: Walk-forward dels millors ────────────────────────────────────

    if winners:
        print(f"\n\n{'=' * 100}")
        print("PART 3: WALK-FORWARD VALIDATION (3 folds) dels millors")
        print("=" * 100)

        for r in winners[:5]:
            wf = walk_forward(candles, r.classifier, r.depth, r.target, min_n=30)
            print(f"\n  {r.classifier} d={r.depth} tgt={r.target}")
            print(f"  Walk-forward OOS agregat: {wf['oos_trades']} trades, "
                  f"WR={wf['oos_wr']:.1f}%, avg={wf['oos_avg']:+.2f}$/trade")
            for fold_name, fold_res in wf["folds"]:
                print(f"    {fold_name}: IS {fold_res.is_trades}t/{fold_res.is_avg:+.2f}$/t "
                      f"→ OOS {fold_res.oos_trades}t/{fold_res.oos_avg:+.2f}$/t "
                      f"WR={fold_res.oos_wr:.1f}% (sig grams: {fold_res.n_grams_significant})")

    # ── PART 4: Experiment especial — bigram 4 estats + any_green + tendència EMA
    print(f"\n\n{'=' * 100}")
    print("PART 4: EXPERIMENT ESPECIAL — Bigrams + filtre tendència EMA")
    print("=" * 100)

    # Afegir EMA200 com a filtre de règim (no com a estat)
    # Calculem EMA200 sobre el close
    closes = np.array([c.c for c in candles])
    ema200 = np.zeros(len(closes))
    ema200[0] = closes[0]
    alpha = 2.0 / 201.0
    for i in range(1, len(closes)):
        ema200[i] = alpha * closes[i] + (1 - alpha) * ema200[i - 1]

    # Experiment: bigram 4st + any_green, FILTRAT per close > EMA200 (bull)
    print("\n  Bigram 4st + target=any_green, FILTRAT per close > EMA200 (tendència alcista)")
    print("  ─" * 40)

    # Recalcular amb filtre
    c_is_bull = [c for i, c in enumerate(candles) if c.ts <= is_end and i >= 200 and closes[i] > ema200[i]]
    c_oos_bull = [c for i, c in enumerate(candles) if c.ts >= oos_start and i >= 200 and closes[i] > ema200[i]]
    c_is_bear = [c for i, c in enumerate(candles) if c.ts <= is_end and i >= 200 and closes[i] <= ema200[i]]
    c_oos_bear = [c for i, c in enumerate(candles) if c.ts >= oos_start and i >= 200 and closes[i] <= ema200[i]]

    for regime, c_is_r, c_oos_r in [("BULL (c>EMA200)", c_is_bull, c_oos_bull),
                                     ("BEAR (c<EMA200)", c_is_bear, c_oos_bear)]:
        print(f"\n  Règim: {regime}")
        print(f"  IS: {len(c_is_r)} candles, OOS: {len(c_oos_r)} candles")

        # Construir bigrams manualment
        for tgt_name, tgt_fn in [("any_green", target_any_green),
                                  ("strong_green", target_strong_green)]:
            br_is = sum(1 for c in c_is_r if tgt_fn(c)) / len(c_is_r) if c_is_r else 0
            br_oos = sum(1 for c in c_oos_r if tgt_fn(c)) / len(c_oos_r) if c_oos_r else 0

            # Bigrams
            gram_is: dict[str, list[float]] = defaultdict(list)
            for i in range(2, len(c_is_r)):
                gram = f"{c_is_r[i-2].states['4st']}|{c_is_r[i-1].states['4st']}"
                gram_is[gram].append(c_is_r[i].move_pct)

            gram_oos: dict[str, list[float]] = defaultdict(list)
            for i in range(2, len(c_oos_r)):
                gram = f"{c_oos_r[i-2].states['4st']}|{c_oos_r[i-1].states['4st']}"
                gram_oos[gram].append(c_oos_r[i].move_pct)

            sig_grams = []
            for gram, moves_is in gram_is.items():
                n = len(moves_is)
                if n < 20:
                    continue
                hits = sum(1 for m in moves_is if tgt_fn_from_move(m, tgt_name))
                wl = wilson_lower(hits, n)
                if wl > br_is:
                    p_is = hits / n
                    moves_oos = gram_oos.get(gram, [])
                    n_oos = len(moves_oos)
                    hits_oos = sum(1 for m in moves_oos if tgt_fn_from_move(m, tgt_name))
                    p_oos = hits_oos / n_oos if n_oos > 0 else 0
                    avg_move_is = np.mean(moves_is)
                    avg_move_oos = np.mean(moves_oos) if moves_oos else 0
                    sig_grams.append((gram, n, p_is, n_oos, p_oos,
                                      avg_move_is, avg_move_oos))

            sig_grams.sort(key=lambda x: x[5], reverse=True)

            if sig_grams:
                print(f"\n    Target: {tgt_name} (base rate IS={br_is:.1%}, OOS={br_oos:.1%})")
                print(f"    {'Gram':<12} {'N_IS':>5} {'P_IS':>6} {'Mv_IS':>8} "
                      f"{'N_OOS':>6} {'P_OOS':>7} {'Mv_OOS':>8} {'$/t OOS':>8}")
                print(f"    {'─' * 65}")
                for gram, n_is, p_is, n_oos, p_oos, mv_is, mv_oos in sig_grams:
                    pnl_oos = NOMINAL * mv_oos - FEE if n_oos > 0 else 0
                    print(f"    {gram:<12} {n_is:>5} {p_is:>5.1%} {mv_is*100:>+7.3f}% "
                          f"{n_oos:>6} {p_oos:>6.1%} {mv_oos*100:>+7.3f}% {pnl_oos:>+7.2f}$")

    # ── RESUM FINAL ──────────────────────────────────────────────────────────
    print(f"\n\n{'=' * 100}")
    print("RESUM EXECUTIU")
    print("=" * 100)

    if winners:
        best = winners[0]
        print(f"\n  Millor combinació IS→OOS:")
        print(f"    Classifier: {best.classifier}, Depth: {best.depth}, Target: {best.target}")
        print(f"    IS:  {best.is_trades}t, WR={best.is_wr:.1f}%, avg={best.is_avg:+.2f}$/trade")
        print(f"    OOS: {best.oos_trades}t, WR={best.oos_wr:.1f}%, avg={best.oos_avg:+.2f}$/trade")
    else:
        print("\n  Cap combinació amb OOS positiu i N >= 20")
        print("  Markov pur (seqüències de candles) no té prou edge per ETH 4H")

    print(f"\n  Conclusions:")
    print(f"  - El base rate de 'green' és ~50% → difícil de batre significativament")
    print(f"  - Menys estats + IC Wilson redueixen overfitting però també edge")
    print(f"  - El filtre de règim (EMA200) pot ajudar a separar bull/bear")
    print(f"  - Possible next: afegir volum o volatilitat com a dimensió extra")


def tgt_fn_from_move(move_pct: float, tgt_name: str) -> bool:
    """Aproximació del target basada en move_pct (sense accés a OHLC complet)."""
    if tgt_name == "any_green":
        return move_pct > 0
    elif tgt_name == "strong_green":
        return move_pct > 0.005
    elif tgt_name == "clean_green":
        return move_pct > 0.003  # aproximació
    elif tgt_name == "green_low_dd":
        return move_pct > 0  # aproximació (no tenim low)
    return move_pct > 0


if __name__ == "__main__":
    main()
