# Capitulation Scalp 1H — Regles operatives

Actualitzat: 2026-03-15
Scripts: `lab/explore/eth_scalp_final.py`, `eth_scalp_markov_v4.py`
Backtest: Binance 1H, 2017-08 → 2026-03 (75k candles per asset crypto)

## Resum executiu

**TF únic: 1H. Direcció: LONG only. SHORT no funciona a cap asset.**

LONG després d'un crash extrem en 1H. Lògica: capitulació → rebot.
Funció `entry(asset, candle_1h, indicators)` → `(LONG, score, MFE, MAE) | None`

### Versió òptima: P1 (100x + paper mode after 2 losses)

| Mètrica | Valor |
|---------|-------|
| **WR** | **67%** |
| **PF** | **2.5** |
| **Capital** | **250$ → 11.308$ (x45)** |
| Trades | 207 en 9 anys (ETH+BTC+SOL) |
| Anys positius | **8 de 9** (2024: -314$ = -2.9% dd sobre capital) |
| Max 1 posició | Sí (1 trade per candle, no apilar) |

### Gestió de risc (clau)

```
NO STOP LOSS — el rebot necessita espai per passar
LEVERAGE ADAPTATIU PER SCORE:
  Entry: leverage 100x per tots els scores (P1 versió)

PAPER MODE (circuit breaker):
  Després de 2 pèrdues consecutives → paper trading
  Es torna a real quan el primer senyal en paper seria guanyador
  Efecte: elimina 2023 negatiu (de -211$ a +62$), redueix clustering de pèrdues

1 POSICIÓ MÀXIMA:
  Si hi ha trade obert, no es pot obrir un altre
  Redueix riscos en crashes prolongats (múltiples senyals consecutius)
```

### Resultats backtest P1 (250$ → compounding)

| Any | N | WR | Total$ | Lev avg |
|-----|---|-----|--------|---------|
| 2018 | 40 | 75% | +3.069$ | 100x |
| 2019 | 9 | 56% | +140$ | 100x |
| 2020 | 29 | 59% | +1.534$ | 100x |
| 2021 | 53 | 66% | +4.331$ | 100x |
| 2022 | 41 | 61% | +850$ | 100x |
| **2023** | **9** | **67%** | **+62$** | 100x |
| **2024** | **8** | **62%** | **-314$** | 100x |
| 2025 | 16 | 88% | +1.238$ | 100x |
| 2026 | 2 | 100% | +149$ | 100x |

**2024 = únic any negatiu** (-314$ sobre ~11.000$ capital = drawdown 2.9%).
Amb N=8 i WR 62%, probabilitat d'any negatiu amb tan pocs trades és inevitable (~15%).

---

## Condicions d'entrada

**TOTES** han de ser TRUE a la candle 1H actual:

| # | Condició | Lògica |
|---|----------|--------|
| 1 | **Body < -3%** | Candle 1H amb caiguda > 3% (crash) |
| 2 | **Close < BB lower(20, 2.0)** | Preu fora de 2 desviacions estàndard |
| 3 | **Drop acumulat 3h > -5%** | Caiguda >5% en les últimes 3 hores |
| 4 | **Hora UTC NOT in {16,17,18,19}** | Evitar US afternoon (WR 53% vs 70%+) |
| 5 | **Vol_rel <= 5x** | No entrar en pànic extrem (WR 49%) |

**Execució:**
- LONG a l'OPEN de la SEGÜENT candle 1H
- Exit al CLOSE de la mateixa candle (1H hold)
- 1 posició màxima (no apilar)

---

## Funció entry() → (direction, score, expected_MFE, expected_MAE)

### Scoring (0-8 punts)

```python
ASSET_CONFIG = {
    'ETH': (-0.03, -0.05, 3.36),
    'BTC': (-0.03, -0.05, 3.36),
    'SOL': (-0.03, -0.05, 3.36),
}

def entry(asset, body_pct, bb_lower, close, drop3h, rsi7, vol_rel, hour):
    """
    Capitulation Scalp 1H entry function.
    Returns ('LONG', score, expected_mfe, expected_mae) or None.
    """
    if asset not in ASSET_CONFIG:
        return None
    body_th, drop_th, fee = ASSET_CONFIG[asset]

    # Condicions base
    if body_pct >= body_th: return None
    if close >= bb_lower: return None
    if drop3h >= drop_th: return None
    if hour in (16, 17, 18, 19): return None
    if vol_rel > 5: return None

    # Scoring
    score = 0
    if body_pct < body_th * 2.5: score += 2
    elif body_pct < body_th * 1.5: score += 1
    if drop3h < drop_th * 2.5: score += 2
    elif drop3h < drop_th * 1.5: score += 1
    if rsi7 < 15: score += 2
    elif rsi7 < 25: score += 1
    if vol_rel > 3: score += 1
    if hour in (20, 21): score += 1

    # Expected MFE/MAE per tier
    if score >= 5:
        return ('LONG', score, 0.0524, 0.0427)   # HIGH: WR~72%
    elif score >= 3:
        return ('LONG', score, 0.0288, 0.0221)   # MID:  WR~66%
    else:
        return ('LONG', score, 0.0235, 0.0232)   # LOW:  WR~65%
```

### Resultats per tier (ETH 210 trades)

| Tier | Score | N | WR | Avg MFE | Avg MAE | Avg $/t |
|------|-------|---|-----|---------|---------|---------|
| LOW | 0-2 | 85 | 65% | +2.35% | 2.32% | +15.6$ |
| **MID** | **3-4** | **89** | **66%** | **+2.88%** | **2.21%** | **+35.4$** |
| **HIGH** | **5+** | **36** | **72%** | **+5.24%** | **4.27%** | **+105.8$** |

---

## Paper mode (circuit breaker)

```
ESTAT: REAL o PAPER

Transicions:
  REAL → PAPER: si 2 pèrdues consecutives
  PAPER → REAL: si el primer senyal en paper hauria guanyat (move > 0)

En mode PAPER:
  - El senyal es detecta normalment (entry() retorna LONG)
  - S'observa el resultat però NO s'obre posició real
  - Si el trade hauria guanyat → tornar a REAL
  - Si hauria perdut → seguir en PAPER
```

Efecte al backtest: 2023 passa de -211$ a +62$. Redueix 30 trades (de 237 a 207).

---

## Assets validats

| Asset | N | WR | PF | W/L | Total | 2024+ OOS |
|-------|---|-----|-----|-----|-------|-----------|
| **ETH** | 210 | **67%** | **2.7** | 1.53 | +8.281$ | 74% (N=27) |
| **BTC** | 110 | **71%** | **3.3** | 1.40 | +5.537$ | 100% (N=3) |
| **SOL** | 200 | 60% | 1.6 | 1.14 | +5.060$ | 67% (N=42) |

**Descartats a 1H**: NVDA, MSFT, NQ (funcionen a D1 → altra estratègia), XAU (poc historial)
**Descartats sempre**: SHORT (WR 52%, EV negatiu en tots els assets)

---

## Lookup taules per l'agent de tancament

**Per severitat crash:**

| Body | N | WR | MFE avg | MAE avg |
|------|---|-----|---------|---------|
| [-5%,-3%) lleu | 116 | 66% | +2.12% | 2.08% |
| [-8%,-5%) fort | 69 | 67% | +3.38% | 2.22% |
| [-15%,-8%) crash | 23 | 70% | +6.28% | 6.14% |

**Per drop acumulat 3h:**

| Drop 3h | N | WR | MFE avg | MAE avg |
|---------|---|-----|---------|---------|
| [-8%,-5%) | 136 | 60% | +1.87% | 2.18% |
| [-12%,-8%) | 55 | **80%** | +4.40% | 2.33% |
| [-20%,-12%) | 16 | 69% | +6.31% | 5.29% |

**Per franja horària:**

| Franja UTC | WR | PF | Acció |
|------------|-----|-----|-------|
| **00-03 Asia** | **72%** | **4.1** | Entrar |
| 04-07 Asia late | 62% | 2.6 | Entrar |
| 08-11 EU morning | 73% | 1.8 | Entrar |
| 12-15 EU/US overlap | 65% | 2.3 | Entrar |
| **16-19 US afternoon** | **53%** | **1.9** | **NO ENTRAR** |
| **20-23 US close** | **73%** | **4.2** | **Entrar (millor)** |

**Per volum:**

| Volum relatiu | WR | Acció |
|---------------|-----|-------|
| Normal (<1.5x) | 85% | Entrar |
| Alt (1.5-3x) | 72% | Entrar |
| Molt alt (3-5x) | 68% | Entrar (score +1) |
| **Pànic (>5x)** | **49%** | **NO ENTRAR** |

---

## Sizing

```
col = min(max(capital * 0.20, 15$), 60$)
leverage = 100x
nominal = col * lev
fee = 3.36$ per trade

IMPORTANT: MAE avg 2.6% amb 100x lev sobre col 40$ → drawdown pot superar col.
Risc de liquidació real. Sizing conservador (col >= 20% capital) és crític.
```

---

## Limitacions i riscos

1. **N baix per any**: ~25 trades/any combinats → trading d'events, no scalping HF
2. **Clustering**: múltiples senyals en pocs dies durant crashes, res durant mesos
3. **Liquidació**: MAE pot superar col·lateral amb 100x → sizing conservador obligatori
4. **2024 negatiu**: -314$ amb N=8 (inevitable amb P(any neg | N=8, WR=65%) ≈ 15%)
5. **No SL**: el rebot necessita espai, SL mata l'estratègia (backtest provat, destrueix capital)
6. **Depèn de volatilitat crypto**: si crypto es calma (com BTC 2025-2026), menys senyals

---

## Next steps per a bot automàtic Ostium

### 1. Implementació bot
- [ ] Connectar amb Ostium SDK/API per executar trades
- [ ] Websocket/polling Binance 1H candles (ETH, BTC, SOL)
- [ ] Calcular indicadors en temps real (BB20, RSI7, drop3h, vol_rel)
- [ ] Executar entry() cada candle → si senyal → open LONG Ostium
- [ ] Paper mode state machine

### 2. Validació robustesa
- [ ] Forward test 1 mes en paper (sense capital real)
- [ ] Comparar senyals real-time vs backtest per les mateixes candles
- [ ] Verificar fees Ostium reals vs estimades (3.36$)
- [ ] Test latència: el bot pot entrar a l'open de la candle següent?

### 3. Millores futures
- [ ] Agent de tancament intel·ligent (usar MFE/MAE per TP/trailing)
- [ ] Integrar amb Portfolio D (NVDA dilluns etc.) per diversificació
- [ ] D1 strategy per NVDA/MSFT/NQ (mateixa lògica, altre TF)
- [ ] Alertes Telegram/Discord quan salta senyal

---

*Generat: 2026-03-15. Backtest: Binance ETHUSDT + BTCUSDT + SOLUSDT 1H 2017-2026.*
