# LAB_RESUM_COMPLET.md — Resum executiu de la fase LAB

Data tancament LAB: 2026-03-16
Projecte: TradingAgent — Ostium DEX Perps

---

## 1. Objectiu de la fase LAB

Trobar setups de trading amb **edge estadísticament robust** per operar al DEX Ostium
(perpetuals sintètics sobre equitats, crypto, índexs, commodities).

**Gate per sortir del LAB**: ≥1 setup `ACCEPTED_D1_ASSET` o ≥2 famílies `WATCHLIST` amb EV>0,
paper probe autoritzat per `PAPER_PROBE_AUTHORIZED`.

**Capital operatiu**: 250$, leverage 20x, fee Ostium 5.38$/trade.

---

## 2. Exploració completa — 7 cicles (T6 → T6g)

### 2.1 Visió general de terrenys

| Cicle | Terreny | Assets | Setups | ACCEPTED | WATCHLIST | REJECTED |
|-------|---------|--------|--------|----------|-----------|----------|
| T6    | Crypto 1H   | ETH, BTC, SOL | 7 | 0 | 1 | 6 |
| T6b   | Crypto 4H   | ETH, BTC, SOL | 6 | 0 | 0 | 6 |
| T6c   | Equitats D1 (multi-setup) | 8 assets | 6 | 0 | 1 | 5 |
| T6d   | Equitats D1 (per asset, leverage sweep) | MSFT,NVDA,QQQ,AAPL,META,AMZN,GOOGL,SPX | 1 | **1** | 2 | 5 |
| T6e   | Gate D1 adaptat + decisió final | — | — | — | — | PAPER_PROBE_AUTHORIZED |
| T6f   | Nous assets equitats D1 | AMD,NFLX,META,GOOGL,AMZN | 1 | 0 | 0 | 5 |
| T6g   | Commodities + índexs D1 | GLD,SPY,^GDAXI | 1 | 0 | 1* | 2 |

*SPY: WATCHLIST però N=24 insuficient per probe independent.

**Total explorat**: 3 terrenys, 28+ setups, 20+ assets individuals.

---

### 2.2 Per terreny: per què funciona o no

#### Crypto 1H — WATCHLIST modest
- **Funciona**: capitulació extrema (body<-3%, BB lower, drop 3H>5%) → rebot
- **Limitació**: 14% liquidacions a 20x (MAE mediana 1.5%), EV modesti (+4-5$/t)
- **CAGR simulat**: 19% en 8.6 anys (250$→1.114$)
- **Decisió**: no suficient sol per BUILD, útil com a complement de portfolio

#### Crypto 4H — Tots REJECTED
- **Per què**: MAE 3-5% >> liq threshold 5% a 20x → liq rate 22-38%
- **Insight**: crypto 4H és massa volàtil per leverage fix a 20x

#### Patrons TA clàssics (crypto 1H) — Tots REJECTED
- BB squeeze, ATR breakout, hammer, sweep reclaim, pullback EMA20
- **Per què**: fees fixes de 5.38$ massa altes per moves típics de patrons TA
- **MC shuffle = 0%** per a tots → cap edge estadístic

#### Equitats D1 — EL TERRENY
- **Per què funciona**: move D1 de 2-3% cobreix millor les fees vs crypto 1H
- **MAE D1 < MAE 4H crypto** per a grans caps → menys liquidacions
- **Tesi**: mega-cap tech de software/hardware → "V-shape recovery" després de pànics
  institucionals (buybacks, absorció de smart money, Fed put)

---

### 2.3 Resultats definitius per asset (capitulation_d1, 20x)

| Asset | N | tpy | WR_b | EV@20x | Liq | WF | MC | MAE | Status |
|-------|---|-----|------|--------|-----|-----|-----|-----|--------|
| **MSFT** | **41** | **3.4** | **78%** | **+12.7$** | **0%** | **10/12** | **100%** | **0.75%** | **ACCEPTED_D1_ASSET** |
| NVDA | 68 | 5.2 | 63% | +6.0$ | 4.4% | 11/13 | 100% | 1.55% | WATCHLIST |
| QQQ  | 40 | 3.3 | 62% | +3.6$ | 2.5% | 7/8  | 100% | 1.32% | WATCHLIST |
| SPY  | 24 | 2.0 | 75% | +2.9$ | 4.2% | 8/9  | 100% | 1.02% | WATCHLIST (N baix) |
| AAPL | 30 | 2.5 | 50% | -2.4$ | 3.3% | 4/9  | 100% | 1.18% | REJECTED |
| NFLX | 70 | 5.0 | 59% | -3.2$ | 7.1% | 11/14| 100% | 1.40% | REJECTED |
| META | 63 | 5.2 | 60% | -3.3$ | 6.3% | 8/12 | 100% | 1.26% | REJECTED |
| GOOGL| 50 | 3.8 | 56% | -4.2$ | 2.0% | 8/12 | 100% | 1.20% | REJECTED |
| AMZN | 62 | 4.8 | 53% | -5.7$ | 6.5% | 8/12 | 100% | 1.69% | REJECTED |
| AMD  | 104| 8.0 | 46% | -14.3$ | 16.3%| 6/13 | 0%  | 2.00% | REJECTED |
| GLD  | 3  | 0.4 | 67% | +16.6$ | 0%  | 2/3  | 100% | 0.54% | REJECTED (N=3) |
| ^GDAXI|37 | 3.1 | 51% | -4.8$ | 0%  | 7/11 | 100% | 0.89% | REJECTED |

---

## 3. El setup: capitulation_d1

**Definició canònica** (sense canvis des de T6c):
```python
body_pct = (close - open) / open    # candle bajista
signal = body_pct < -0.02           # body > -2%
     AND close < BB_lower(20, 2)    # trenca Bollinger inferior
entry  = open[t+1]                  # entrada: open del dia següent
exit   = close[t+1]                 # sortida: close del dia següent
```

**Paràmetres operatius**:
- Leverage: 20x
- Collateral: 20% del capital (min 15$, max 60$)
- Fee: 5.38$ per trade (Ostium)
- Liquidació simulada si MAE ≥ 5% (1/20)

**Per què funciona a MSFT**:
- Mega-cap software: market makers actius, recompres corporatives, menys risc fonamental
- MAE mediana 0.75% → quasi zero liquidacions a 20x
- "Pànics institucionals" (vendes de momentum/CTA) → smart money absorbeix ràpidament

**Per què NO funciona en altres**:
- AMD, AMZN, META, GOOGL: MAE massa alta o WR massa baixa en bear markets prolongats
- Crypto: MAE 3-5% D1, liq rate >20%
- DAX, NFLX: sense el "V-shape recovery" estructural del mercat US

---

## 4. Gate D1 per asset (definit a T6e)

| Criteri | Valor mínim | Justificació |
|---------|------------|--------------|
| N | ≥35 | ~3-4 anys de dades a 3-5 senyals/any |
| WR baseline | ≥60% | Edge real sobre random |
| EV deployable | ≥+8$/trade | Cobreix fees + risc a 20x |
| PF deployable | ≥1.8 | Ratio guany/pèrdua sòlid |
| Liq rate @20x | ≤5% | Max 1 liq cada 20 trades |
| WF % anys positius | ≥70% | Consistència temporal |
| MC shuffle | ≥90% | Edge no aleatori |
| MAE mediana | ≤1.5% | Control de risc intraday |

*El gate general N≥120 no és aplicable a setups D1 per asset (freqüència estructuralment baixa).*

---

## 5. Rendiment simulat (capital 250$, leverage 20x)

### Per asset (sense compounding, col_max=60$)

| Asset | CAGR simulat | Capital final | Anys |
|-------|-------------|--------------|------|
| MSFT  | ~10%        | 772$         | 12a  |
| NVDA  | ~8%         | 657$         | 13a  |
| QQQ   | ~4%         | 392$         | 12a  |
| Crypto 1H | ~19%   | 1.114$       | 8.6a |

### Portfolio combinat (MSFT + NVDA + QQQ, sense compounding)

- ~12 senyals/any (3.4 MSFT + 5.2 NVDA + 3.3 QQQ)
- EV ponderat: ~+7.4$/trade
- Guany any 1: ~+89$/any (+35% sobre 250$)
- **CAGR simulat: ~21%** (amb plateau de col_max=60$)

### Amb compounding gradual (escalar COL_MAX manualment)

| Mode | Capital mediana 12a | CAGR mediana |
|------|---------------------|-------------|
| Fixed max 60$ | 1.551$ | 15.5% |
| Scale gradual (max 150$) | 4.070$ | 24.7% |
| Compounding pur 20% | 52.903$ | 52.8% |

*Compounding pur: alta dispersió (P10=17k$, P90=76k$). Ruïna 4%.*
*Estimació real (degradació 30% vs backtest): 14-20% CAGR amb fixed max.*

---

## 6. Decisió final de la fase LAB

### ✅ PAPER_PROBE_AUTHORIZED

**Condició complerta**: MSFT = `ACCEPTED_D1_ASSET` (8/8 criteris del gate D1).

### Univers recomanat per al paper probe

```
PILLAR (primari):   MSFT — capitulation_d1, 20x
OPCIONAL:           NVDA — si no hi ha senyal MSFT actiu
OPCIONAL:           QQQ  — índex de diversificació
```

**SPY** pot substituir QQQ si la disponibilitat a Ostium ho permet (tokens iguals).

### Paràmetres del paper probe

```
Durada mínima:  4 setmanes de mercat actiu
Leverage:       20x (fix)
Collateral:     20% del capital (max 60$)
Setup:          capitulation_d1 (body<-2% + BB lower)
Sortida:        close del dia T+1 (igual que backtest)
Paper mode:     2 losses consecutives → mode paper fins 1 win en paper
```

---

## 7. Insights clau del LAB

1. **Patrons TA clàssics no funcionen** amb fees fixes d'Ostium (~5$).
   Calen setups de baixa freqüència amb moves grans (>2% D1).

2. **La família "capitulation" és l'única que mostra edge** en múltiples terrenys.
   Mean-reversion post-crash és l'única tesi que sobreviu les fees.

3. **L'edge és específic al mercat US mega-cap**. DAX, FAANG, AMD no el comparteixen.
   La raó: buybacks corporatius + "Fed put" + market makers agressius a US.

4. **Leverage 100x és inviable** (T1: 61% liquidacions, capital destruït).
   **20x és l'òptim**: liq rate < 5% per als 3 assets WATCHLIST+.

5. **Gold (XAU) mereix un follow-up** amb body<-1.5% (3 senyals en 13a a -2% és
   estadísticament irrellevant però conceptualment correcte).

6. **NFLX és el millor cas fallit**: MC=100%, WF=11/14=79%, però liq=7.1% trenca
   l'EV. A 15x podria ser viable. Candidat per futur LAB si s'explora leverage adaptatiu.

---

## 8. Fase següent: T7 — Paper Probe Mínim

Objectiu: validar en temps real que el sistema genera senyals correctament i que
l'execució paper coincideix amb les prediccions del backtest.

**No és un BUILD complet.** És un pilot de 4+ setmanes per verificar:
- El sistema detecta correctament els senyals capitulation_d1 en MSFT
- Les entrades/sortides paper coincideixen amb les prediccions
- El winrate observat és compatible amb el 78% backtest (dins intervals de confiança)
- El sistema de paper mode funciona (2 losses → paper, 1 win paper → live)
