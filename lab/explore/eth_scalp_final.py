"""
eth_scalp_final.py — ETH Capitulation Scalp — Anàlisi final + regles operatives

Setup: LONG ETH/USD 1H quan es compleixen:
  1. Body candle actual < -3%
  2. Close < Bollinger Band lower (20, 2.0)
  3. Drop acumulat 3h > -5%
  4. Hora UTC NOT in {16,17,18,19} (filtre opcional)

Entry: LONG a l'open de la SEGÜENT candle 1H
Exit:  Close de la mateixa candle (1H hold)
"""
import json, time, urllib.request
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import warnings; warnings.filterwarnings('ignore')

# Download 1H
all_k = []
start_ms = 0
while True:
    url = (f"https://api.binance.com/api/v3/klines?symbol=ETHUSDT"
           f"&interval=1h&startTime={start_ms}&limit=1000")
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
    rows.append({"ts": ts, "O": float(k[1]), "H": float(k[2]),
                 "L": float(k[3]), "C": float(k[4]), "V": float(k[5])})
df = pd.DataFrame(rows).set_index("ts")
C = df["C"].values; O = df["O"].values; H = df["H"].values; L = df["L"].values
N = len(df)
print(f"{N} candles 1H\n")

body_pct = (C - O) / np.maximum(O, 1)


def bb_lower(c, p=20, m=2.0):
    lo = np.full(len(c), np.nan)
    for i in range(p - 1, len(c)):
        w = c[i - p + 1: i + 1]
        lo[i] = np.mean(w) - m * np.std(w, ddof=0)
    return lo


def acc_drop(k):
    d = np.zeros(N)
    for i in range(k, N):
        d[i] = (C[i] - C[i - k]) / C[i - k]
    return d


bb_lo = bb_lower(C, 20, 2.0)
drop3h = acc_drop(3)

NOM = 4000
FEE = 3.36
BAD_HOURS = {16, 17, 18, 19}


def setup_a(i):
    return (body_pct[i] < -0.03
            and not np.isnan(bb_lo[i]) and C[i] < bb_lo[i]
            and drop3h[i] < -0.05)


def setup_b(i):
    return setup_a(i) and df.index[i].hour not in BAD_HOURS


for version, sfn, vname in [("A", setup_a, "SENSE filtre horari"),
                              ("B", setup_b, "AMB filtre horari (excloent 16-19 UTC)")]:
    print(f"\n{'x' * 110}")
    print(f"  VERSIO {version}: {vname}")
    print(f"{'x' * 110}")

    all_trades = []
    for i in range(200, N - 1):
        if not sfn(i):
            continue
        o1 = O[i + 1]; h1 = H[i + 1]; l1 = L[i + 1]; c1 = C[i + 1]
        move = (c1 - o1) / o1
        pnl = NOM * move - FEE
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1
        green = c1 > o1
        rng1 = h1 - l1
        ideal = (green and rng1 > 0
                 and (o1 - l1) / rng1 < 0.20 and (h1 - c1) / rng1 < 0.20
                 and move > 0.002)
        all_trades.append({
            "ts": df.index[i], "yr": df.index[i].year, "hour": df.index[i].hour,
            "price": C[i], "move": move, "pnl": pnl, "mae": mae, "mfe": mfe,
            "green": green, "ideal": ideal,
        })

    tdf = pd.DataFrame(all_trades)

    # Per any
    print(f"\n  DETALL PER ANY (col=40$, lev=100x, nom={NOM}$, fee={FEE}$)")
    hdr = (f"  {'Any':>6} {'N':>4} {'WR':>5} {'Avg$':>8} {'Total$':>9} {'PF':>5} "
           f"{'AvgW$':>7} {'AvgL$':>7} {'W/L':>5} {'MaxDD$':>7} {'AvgMAE':>7}")
    print(hdr)
    print(f"  {'---' * 28}")

    total_pnl = 0
    all_yearly = []
    for yr in sorted(tdf["yr"].unique()):
        ydf = tdf[tdf["yr"] == yr]
        ny = len(ydf)
        wr = 100 * ydf["green"].mean()
        avg = ydf["pnl"].mean()
        tot = ydf["pnl"].sum()
        w = ydf[ydf["pnl"] > 0]["pnl"]
        l = ydf[ydf["pnl"] <= 0]["pnl"]
        pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99
        aw = w.mean() if len(w) > 0 else 0
        al_v = l.mean() if len(l) > 0 else 0
        wl = abs(aw / al_v) if al_v != 0 else 99
        maxdd = NOM * ydf["mae"].max()
        am = 100 * ydf["mae"].mean()
        flag = " <-OOS" if yr >= 2024 else ""
        all_yearly.append((yr, ny, wr, avg, tot, pf))
        print(f"  {yr:>6} {ny:>4} {wr:>4.0f}% {avg:>+7.1f}$ {tot:>+8.0f}$ {pf:>4.1f} "
              f"{aw:>+6.0f}$ {al_v:>+6.0f}$ {wl:>4.2f} {maxdd:>6.0f}$ {am:>6.2f}%{flag}")
        total_pnl += tot

    w = tdf[tdf["pnl"] > 0]["pnl"]
    l = tdf[tdf["pnl"] <= 0]["pnl"]
    pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99
    print(f"  {'---' * 28}")
    print(f"  {'TOTAL':>6} {len(tdf):>4} {100 * tdf['green'].mean():>4.0f}% "
          f"{tdf['pnl'].mean():>+7.1f}$ {total_pnl:>+8.0f}$ {pf:>4.1f} "
          f"{w.mean():>+6.0f}$ {l.mean():>+6.0f}$")
    pos_y = sum(1 for _, _, _, _, t, _ in all_yearly if t > 0)
    neg_y = sum(1 for _, _, _, _, t, _ in all_yearly if t <= 0)
    print(f"  Anys positius: {pos_y}/{pos_y + neg_y}")

    # Distribució
    print(f"\n  DISTRIBUCIO PnL:")
    print(f"    Avg win:    {w.mean():>+8.1f}$ (move: +{100 * tdf[tdf['green']]['move'].mean():.3f}%)")
    print(f"    Avg loss:   {l.mean():>+8.1f}$ (move: {100 * tdf[~tdf['green']]['move'].mean():.3f}%)")
    print(f"    W/L ratio:  {abs(w.mean() / l.mean()):.2f}")
    print(f"    Best:       {tdf['pnl'].max():>+8.1f}$")
    print(f"    Worst:      {tdf['pnl'].min():>+8.1f}$")
    print(f"    Median:     {tdf['pnl'].median():>+8.1f}$")
    for p in [10, 25, 50, 75, 90]:
        print(f"    P{p}:        {np.percentile(tdf['pnl'], p):>+8.1f}$")

    # MAE / MFE
    print(f"\n  MAE: avg={100 * tdf['mae'].mean():.2f}% (${NOM * tdf['mae'].mean():.0f})  "
          f"max={100 * tdf['mae'].max():.2f}% (${NOM * tdf['mae'].max():.0f})")
    print(f"  MFE: avg={100 * tdf['mfe'].mean():.2f}% (${NOM * tdf['mfe'].mean():.0f})  "
          f">1%: {100 * np.mean(tdf['mfe'] > 0.01):.0f}%")

    # Walk-forward
    print(f"\n  WALK-FORWARD (per any):")
    print(f"  {'Test':>6} {'N':>4} {'WR':>5} {'Avg$':>8} {'Total$':>9} {'PF':>5}")
    print(f"  {'---' * 15}")
    wf_pnl = 0
    wf_n = 0
    for test_yr in range(2020, 2027):
        wf = tdf[tdf["yr"] == test_yr]
        if len(wf) == 0:
            continue
        ny = len(wf)
        wr = 100 * wf["green"].mean()
        avg = wf["pnl"].mean()
        tot = wf["pnl"].sum()
        w2 = wf[wf["pnl"] > 0]["pnl"]
        l2 = wf[wf["pnl"] <= 0]["pnl"]
        pf = abs(w2.sum() / l2.sum()) if len(l2) > 0 and l2.sum() != 0 else 99
        print(f"  {test_yr:>6} {ny:>4} {wr:>4.0f}% {avg:>+7.1f}$ {tot:>+8.0f}$ {pf:>4.1f}")
        wf_pnl += tot
        wf_n += ny
    print(f"  {'---' * 15}")
    if wf_n > 0:
        print(f"  {'WF TOT':>6} {wf_n:>4}       {wf_pnl / wf_n:>+7.1f}$ {wf_pnl:>+8.0f}$")

    # Equity curve
    print(f"\n  EQUITY CURVE (acumulat):")
    cum = 0
    for yr, ny, wr, avg, tot, pf in all_yearly:
        cum += tot
        bar = "=" * max(1, int(cum / 200))
        print(f"    {yr}: {cum:>+8.0f}$ {bar}")

    # Compounding
    print(f"\n  COMPOUNDING (capital=250$, col=20% cap, min 15$, max 60$):")
    capital = 250.0
    for yr, ny, wr, avg, tot, pf in all_yearly:
        yr_trades = tdf[tdf["yr"] == yr].sort_values("ts")
        for _, t in yr_trades.iterrows():
            col = min(max(capital * 0.20, 15), 60)
            nom = col * 100
            real_pnl = nom * t["move"] - FEE
            capital += real_pnl
            if capital < 0:
                capital = 0
        print(f"    {yr}: {ny} trades -> capital={capital:>8.0f}$")


# Regles operatives
print(f"\n\n{'=' * 110}")
print("REGLES OPERATIVES FINALS")
print(f"{'=' * 110}")
print("""
  ESTRATEGIA: ETH Capitulation Scalp (LONG only)

  ASSET:      ETH/USD (Ostium o exchange crypto)
  TIMEFRAME:  1H
  DIRECCIO:   LONG only (SHORT no funciona)

  CONDICIONS D'ENTRADA (TOTES TRUE a la candle actual):
    1. Body < -3%          candle 1H de crash
    2. Close < BB lower    Bollinger Band(20, 2.0)
    3. Drop 3h > -5%       caiguda acumulada ultimes 3 hores
    4. Hora UTC NOT in {16,17,18,19}  evitar US afternoon

  EXECUCIO:
    LONG a l'OPEN de la SEGUENT candle 1H
    Exit al CLOSE de la mateixa candle (1H hold)
    Agent pot: TP parcial si move > +1%, SL manual si -2%

  SIZING:
    Col-lateral: 20% del capital (min 15$, max 60$)
    Leverage: 100x
    Fee: 3.36$/trade

  FREQUENCIA: ~20-25 senyals/any

  CIRCUIT BREAKERS:
    3 losses seguits -> pausa 48h
    Capital < 100$ -> stop total
    Loss > 500$ en un trade -> reduir col a min 15$
""")
