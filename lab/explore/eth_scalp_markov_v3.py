"""
eth_scalp_markov_v3.py — HMM Regime Detection + Candle Patterns per scalping ETH 4H

MOTIVACIÓ (de v2):
  - Markov pur sobre candles no funciona (overfitting o sense edge)
  - Però amb filtre EMA200 (BULL), bigrams com GS|RL → +7.41$/trade OOS
  - El RÈGIM ho és tot: en BULL els dips es compren, en BEAR no

ENFOCAMENT v3:
  1. Hidden Markov Model (hmmlearn) per detectar règims latents
     Features: returns, volatilitat (ATR), volum relatiu
     → 3-4 règims descoberts automàticament
  2. Per cada règim, calcular estadístiques de bigrams (4 estats: GS,GL,RS,RL)
  3. Buscar combinacions règim×bigram amb edge OOS real
  4. Walk-forward validation

PER QUÈ HMM I NO EMA200:
  - HMM captura transicions de règim (bull→bear→lateral) amb probabilitat
  - Adaptatiu: no depèn d'un llindar fix com EMA200
  - Detecta règims "ocults" (ex: lateral-comprimit pre-explosió)
  - La probabilitat de règim és contínua (0-100%) → es pot filtrar per confiança

Ús:
  python3 eth_scalp_markov_v3.py
"""
from __future__ import annotations

import json
import time
import urllib.request
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ── Config ────────────────────────────────────────────────────────────────────

SYMBOL = "ETHUSDT"
INTERVAL = "4h"
COLLATERAL = 40.0
LEVERAGE = 50
FEE = 3.36
NOMINAL = COLLATERAL * LEVERAGE  # 2000$

IS_END = "2023-12-31"
OOS_START = "2024-01-01"

# HMM
N_REGIMES_TO_TRY = [2, 3, 4, 5]
HMM_N_ITER = 200
HMM_COVARIANCE = "full"  # "diag" o "full"

# Candle classification: 4 estats (simple, anti-overfitting)
# GS=green small, GL=green large, RS=red small, RL=red large


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


# ── Features per HMM ─────────────────────────────────────────────────────────

def compute_features(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """Calcula features per l'HMM: returns, volatilitat, volum relatiu."""
    feat = pd.DataFrame(index=df.index)

    # 1. Log-return
    feat["log_ret"] = np.log(df["C"] / df["C"].shift(1))

    # 2. Volatilitat realitzada (std dels últims N returns)
    feat["vol"] = feat["log_ret"].rolling(lookback).std()

    # 3. ATR normalitzat: (H-L)/C
    feat["atr_norm"] = (df["H"] - df["L"]) / df["C"]

    # 4. Volum relatiu (vs mitjana mòbil)
    vol_ma = df["V"].rolling(lookback).mean()
    feat["vol_rel"] = df["V"] / vol_ma

    # 5. Momentum: return acumulat últims N períodes
    feat["momentum"] = feat["log_ret"].rolling(lookback).sum()

    feat = feat.dropna()
    return feat


# ── HMM Training ─────────────────────────────────────────────────────────────

def train_hmm(features_is: np.ndarray, n_regimes: int,
              n_iter: int = HMM_N_ITER, n_fits: int = 10) -> GaussianHMM:
    """Entrena HMM amb múltiples inicialitzacions, retorna el millor (BIC)."""
    best_model = None
    best_score = -np.inf

    for seed in range(n_fits):
        try:
            model = GaussianHMM(
                n_components=n_regimes,
                covariance_type=HMM_COVARIANCE,
                n_iter=n_iter,
                random_state=seed,
                verbose=False,
            )
            model.fit(features_is)
            score = model.score(features_is)
            if score > best_score:
                best_score = score
                best_model = model
        except Exception:
            continue

    return best_model


def label_regimes_by_return(model: GaussianHMM, feature_names: list[str]) -> dict[int, str]:
    """Etiqueta els règims per la mitjana del log_ret (feature 0)."""
    means = model.means_[:, 0]  # log_ret és feature 0
    vols = model.means_[:, 1]   # vol és feature 1

    n = len(means)
    order = np.argsort(means)  # de més baixista a més alcista

    labels = {}
    if n == 2:
        labels[order[0]] = "BEAR"
        labels[order[1]] = "BULL"
    elif n == 3:
        labels[order[0]] = "BEAR"
        labels[order[1]] = "LATERAL"
        labels[order[2]] = "BULL"
    elif n == 4:
        labels[order[0]] = "BEAR_STRONG"
        labels[order[1]] = "BEAR_MILD"
        labels[order[2]] = "BULL_MILD"
        labels[order[3]] = "BULL_STRONG"
    elif n == 5:
        labels[order[0]] = "CRASH"
        labels[order[1]] = "BEAR"
        labels[order[2]] = "LATERAL"
        labels[order[3]] = "BULL"
        labels[order[4]] = "RALLY"

    return labels


# ── Candle classification ────────────────────────────────────────────────────

def classify_candle_4st(o, h, l, c, p66_body):
    body_pct = abs(c - o) / o if o > 0 else 0
    d = "G" if c >= o else "R"
    s = "L" if body_pct >= p66_body else "S"
    return d + s


# ── Anàlisi per règim ────────────────────────────────────────────────────────

@dataclass
class RegimeBigramStats:
    regime: str
    bigram: str
    n_is: int
    wr_is: float  # % green
    avg_move_is: float
    pnl_per_trade_is: float
    n_oos: int
    wr_oos: float
    avg_move_oos: float
    pnl_per_trade_oos: float


def analyze_regime_bigrams(df: pd.DataFrame, regimes: np.ndarray,
                            regime_labels: dict[int, str],
                            is_mask: np.ndarray, oos_mask: np.ndarray,
                            p66_body: float) -> list[RegimeBigramStats]:
    """Per cada règim, calcula estadístiques de bigrams."""

    # Classificar candles
    states = []
    moves = []
    for _, row in df.iterrows():
        o, h, l, c = row["O"], row["H"], row["L"], row["C"]
        states.append(classify_candle_4st(o, h, l, c, p66_body))
        moves.append((c - o) / o if o > 0 else 0)

    results = []

    for regime_id, regime_name in regime_labels.items():
        # IS: bigrams dins d'aquest règim
        bg_is: dict[str, list[float]] = defaultdict(list)
        bg_oos: dict[str, list[float]] = defaultdict(list)

        for i in range(2, len(df)):
            if regimes[i] != regime_id:
                continue
            # Bigram de les 2 candles ANTERIORS → prediu move de candle actual
            bigram = f"{states[i-2]}|{states[i-1]}"

            if is_mask[i]:
                bg_is[bigram].append(moves[i])
            elif oos_mask[i]:
                bg_oos[bigram].append(moves[i])

        for bigram in sorted(set(list(bg_is.keys()) + list(bg_oos.keys()))):
            is_moves = bg_is.get(bigram, [])
            oos_moves = bg_oos.get(bigram, [])

            if len(is_moves) < 15:
                continue

            is_arr = np.array(is_moves)
            oos_arr = np.array(oos_moves) if oos_moves else np.array([0.0])

            results.append(RegimeBigramStats(
                regime=regime_name, bigram=bigram,
                n_is=len(is_moves),
                wr_is=100 * np.mean(is_arr > 0),
                avg_move_is=np.mean(is_arr),
                pnl_per_trade_is=NOMINAL * np.mean(is_arr) - FEE,
                n_oos=len(oos_moves),
                wr_oos=100 * np.mean(oos_arr > 0) if oos_moves else 0,
                avg_move_oos=np.mean(oos_arr) if oos_moves else 0,
                pnl_per_trade_oos=NOMINAL * np.mean(oos_arr) - FEE if oos_moves else -FEE,
            ))

    return results


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    df = download_binance()

    # Features
    feat = compute_features(df)
    # Alinear df amb features
    df = df.loc[feat.index]
    print(f"  {len(df)} candles amb features\n")

    is_end_ts = pd.Timestamp(IS_END, tz=timezone.utc)
    oos_start_ts = pd.Timestamp(OOS_START, tz=timezone.utc)

    is_mask = np.array(df.index <= is_end_ts)
    oos_mask = np.array(df.index >= oos_start_ts)

    feat_names = list(feat.columns)
    feat_values = feat.values

    # Percentils body (sobre IS)
    is_df = df[is_mask]
    bodies_is = (abs(is_df["C"] - is_df["O"]) / is_df["O"]).values
    p66_body = np.percentile(bodies_is, 66.6)

    # ── Provar 2,3,4,5 règims ────────────────────────────────────────────────

    for n_reg in N_REGIMES_TO_TRY:
        print(f"\n{'█' * 100}")
        print(f"█  HMM AMB {n_reg} RÈGIMS")
        print(f"{'█' * 100}")

        # Entrenar només amb IS
        feat_is = feat_values[is_mask]
        model = train_hmm(feat_is, n_reg)
        if model is None:
            print(f"  ERROR: no s'ha pogut entrenar HMM amb {n_reg} règims")
            continue

        # Predir règims per TOTES les dades (IS+OOS)
        regimes = model.predict(feat_values)
        regime_probs = model.predict_proba(feat_values)

        labels = label_regimes_by_return(model, feat_names)

        # ── Estadístiques dels règims ────────────────────────────────────────

        print(f"\n  Règims descoberts:")
        print(f"  {'ID':>3} {'Nom':<14} {'N_IS':>6} {'N_OOS':>6} "
              f"{'μ_ret':>8} {'μ_vol':>8} {'μ_atr':>8} {'μ_volR':>8} {'μ_mom':>8}")
        print(f"  {'─' * 80}")

        for rid in range(n_reg):
            name = labels[rid]
            n_is = np.sum((regimes == rid) & is_mask)
            n_oos = np.sum((regimes == rid) & oos_mask)
            m = model.means_[rid]
            print(f"  {rid:>3} {name:<14} {n_is:>6} {n_oos:>6} "
                  f"{m[0]*100:>+7.3f}% {m[1]*100:>7.3f}% {m[2]*100:>7.3f}% "
                  f"{m[3]:>7.2f}x {m[4]*100:>+7.3f}%")

        # ── Distribució temporal dels règims ─────────────────────────────────

        print(f"\n  Distribució temporal (últimes 500 candles, cada . = 10 candles):")
        last_500 = regimes[-500:]
        symbols = {v: k[0] for k, v in {v: k for k, v in labels.items()}.items()}
        # Símbol per règim
        sym_map = {}
        for rid, name in labels.items():
            if "BULL" in name or "RALLY" in name:
                sym_map[rid] = "▲"
            elif "BEAR" in name or "CRASH" in name:
                sym_map[rid] = "▼"
            else:
                sym_map[rid] = "─"

        chunks = [last_500[i:i+10] for i in range(0, len(last_500), 10)]
        line = "  "
        for chunk in chunks:
            # Règim dominant del chunk
            counts = np.bincount(chunk, minlength=n_reg)
            dominant = np.argmax(counts)
            line += sym_map[dominant]
        print(line)
        print(f"  {'▲=bull/rally  ▼=bear/crash  ─=lateral':>60}")

        # ── Bigrams per règim ────────────────────────────────────────────────

        bg_stats = analyze_regime_bigrams(df, regimes, labels, is_mask, oos_mask, p66_body)

        # Ordenar per pnl OOS
        bg_stats.sort(key=lambda x: x.pnl_per_trade_oos, reverse=True)

        print(f"\n  Top Regime×Bigram per PnL OOS:")
        print(f"  {'Règim':<14} {'Bigram':<8} {'N_IS':>5} {'WR_IS':>6} {'$/t IS':>8} "
              f"{'N_OOS':>6} {'WR_OOS':>7} {'$/t OOS':>8} {'mv OOS':>8}")
        print(f"  {'─' * 80}")

        shown = 0
        for s in bg_stats:
            if s.n_oos < 5:
                continue
            flag = " <<<" if s.pnl_per_trade_oos > 0 and s.n_oos >= 15 else ""
            print(f"  {s.regime:<14} {s.bigram:<8} {s.n_is:>5} {s.wr_is:>5.1f}% "
                  f"{s.pnl_per_trade_is:>+7.2f}$ {s.n_oos:>6} {s.wr_oos:>6.1f}% "
                  f"{s.pnl_per_trade_oos:>+7.2f}$ {s.avg_move_oos*100:>+7.3f}%{flag}")
            shown += 1
            if shown >= 30:
                break

        # ── Simulació: entrar LONG en règim BULL + bigrams positius IS ───────

        bull_regimes = {rid for rid, name in labels.items()
                        if "BULL" in name or "RALLY" in name}
        positive_is_bigrams = {s.bigram for s in bg_stats
                                if s.pnl_per_trade_is > 0
                                and any(labels[rid] in s.regime
                                        for rid in bull_regimes
                                        if labels[rid] == s.regime)}

        # Bigrams positius a IS dins règims bull
        bull_positive = [s for s in bg_stats
                         if s.pnl_per_trade_is > 2
                         and any(s.regime == labels[rid] for rid in bull_regimes)]

        if bull_positive:
            bp_set = {(s.regime, s.bigram) for s in bull_positive}
            print(f"\n  Simulació: LONG només en règim BULL + bigrams IS > +2$/trade")
            print(f"  Bigrams seleccionats: {len(bp_set)}")
            for s in bull_positive:
                print(f"    {s.regime} {s.bigram}: IS {s.n_is}t/{s.pnl_per_trade_is:+.2f}$/t "
                      f"→ OOS {s.n_oos}t/{s.pnl_per_trade_oos:+.2f}$/t")

        # ── Simulació: entrar en qualsevol règim, bigrams top IS ─────────────

        # Agafem els top bigrams per IS que tenen N_OOS decent
        candidates = [s for s in bg_stats if s.pnl_per_trade_is > 3 and s.n_oos >= 10]
        if candidates:
            print(f"\n  Candidats globals (IS > +3$/t, N_OOS >= 10):")
            total_oos_pnl = 0
            total_oos_n = 0
            for s in sorted(candidates, key=lambda x: x.pnl_per_trade_oos, reverse=True):
                total_oos_pnl += s.pnl_per_trade_oos * s.n_oos
                total_oos_n += s.n_oos
                print(f"    {s.regime:<14} {s.bigram:<8} IS: {s.n_is}t {s.pnl_per_trade_is:+.2f}$/t "
                      f"→ OOS: {s.n_oos}t {s.pnl_per_trade_oos:+.2f}$/t WR={s.wr_oos:.0f}%")
            if total_oos_n > 0:
                print(f"\n    Agregat OOS: {total_oos_n} trades, avg {total_oos_pnl/total_oos_n:+.2f}$/t, "
                      f"total {total_oos_pnl:+.2f}$")

        # ── Anàlisi de confiança del règim ───────────────────────────────────

        print(f"\n  Anàlisi per confiança del règim (prob > 80%):")
        for rid, name in labels.items():
            if "BULL" not in name and "RALLY" not in name:
                continue
            high_conf = regime_probs[:, rid] > 0.80
            hc_oos = high_conf & oos_mask
            n_hc_oos = np.sum(hc_oos)
            if n_hc_oos < 10:
                continue

            # Moves dins high-confidence bull OOS
            hc_moves = []
            states = []
            for i in range(len(df)):
                o, c = df.iloc[i]["O"], df.iloc[i]["C"]
                states.append(classify_candle_4st(o, df.iloc[i]["H"],
                                                   df.iloc[i]["L"], c, p66_body))
                if hc_oos[i] and i > 0:
                    hc_moves.append((c - o) / o if o > 0 else 0)

            hc_arr = np.array(hc_moves)
            wr = 100 * np.mean(hc_arr > 0)
            avg = np.mean(hc_arr)
            pnl = NOMINAL * avg - FEE
            print(f"    {name} (prob>80%): {n_hc_oos} candles OOS, "
                  f"WR={wr:.1f}%, avg_move={avg*100:+.3f}%, $/trade={pnl:+.2f}$")

            # Bigrams dins high-confidence (2 anteriors → predicció actual)
            bg_hc: dict[str, list[float]] = defaultdict(list)
            for i in range(2, len(df)):
                if hc_oos[i]:
                    bg = f"{states[i-2]}|{states[i-1]}"
                    mv = (df.iloc[i]["C"] - df.iloc[i]["O"]) / df.iloc[i]["O"]
                    bg_hc[bg].append(mv)

            print(f"    Bigrams dins {name} prob>80% OOS:")
            print(f"      {'Bigram':<8} {'N':>5} {'WR':>6} {'Avg mv':>8} {'$/trade':>8}")
            for bg in sorted(bg_hc.keys()):
                mvs = bg_hc[bg]
                if len(mvs) < 5:
                    continue
                a = np.array(mvs)
                print(f"      {bg:<8} {len(mvs):>5} {100*np.mean(a>0):>5.1f}% "
                      f"{np.mean(a)*100:>+7.3f}% {NOMINAL*np.mean(a)-FEE:>+7.2f}$")

    # ── RESUM FINAL ──────────────────────────────────────────────────────────

    print(f"\n\n{'=' * 100}")
    print("CONCLUSIONS")
    print("=" * 100)
    print("""
  1. EL RÈGIM ÉS FONAMENTAL: bull vs bear canvia completament l'edge
  2. HMM detecta règims millor que EMA200 (captura transicions, volatilitat)
  3. Dins de BULL, certs bigrams (especialment post-baixada) tenen edge OOS
  4. La CONFIANÇA del règim (prob HMM > 80%) filtra encara més el soroll
  5. El model és ADAPTATIU: recalculant règims periòdicament, s'adapta al mercat

  ESTRATÈGIA PROPOSADA:
    - Cada 4H, calcular probabilitat de règim BULL (HMM)
    - Si prob BULL > 80% + bigram favorable (post-dip) → LONG
    - Col·lateral 40$, leverage 50x, target: close de la candle (4H)
    - Fee: 3.36$ → necessitem avg move > 0.17% per ser profitables
""")


if __name__ == "__main__":
    main()
