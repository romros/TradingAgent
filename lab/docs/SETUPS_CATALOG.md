# SETUPS_CATALOG.md — Catàleg de setups per decisió

Actualitzat: 2026-03-16 (T4)

---

## Vista ràpida: setup × asset × tf × status

| # | Setup | Family | Assets | TF ctx/exec | Status | EV/trade | WR | Notes |
|---|-------|--------|--------|-------------|--------|----------|-----|-------|
| **0** | **capitulation_d1** | **capitulation** | **MSFT,NVDA,QQQ** | **D1/D1** | **ACCEPTED_D1_ASSET** | **+12.7$ MSFT** | **78%** | **T7 paper probe actiu. Liq 0%, WF 10/12** |
| 1 | Capitulation Scalp 1H | capitulation | ETH,BTC,SOL | 4H/1H | WATCHLIST | +5.6$ (20x liq) | 59% | Edge real, EV modest. MC 3/3 PASS. 5+/5- anys |
| 2 | Markov HMM Regime | pattern | ETH | 4H/1H | REJECTED | — | — | HMM no detecta bear 2026. Overfitting |
| 3 | Markov pur trigrams | pattern | ETH | 4H/4H | REJECTED | — | — | Overfitting amb qualsevol nombre d'estats |

---

## Detall per setup

### 1. Capitulation Scalp 1H (WATCHLIST)

**Tesi**: Crash extrem 1H (body<-3%, BB lower trencat, drop 3H>5%) → rebot per absorció smart money.

**Validació**:
- MC Shuffle: PASS (100% sims profitables)
- MC Random Entry: PASS (edge +15-35pp > P95)
- MC Param Perturb: PASS (50/50 variants profitables)
- WF: 7/9 expanding, 5/7 rolling
- Liquidació 20x: 14%, EV +5.6$/trade
- Capital: 250$ → 1.114$ en 8.6 anys (x4.5)

**Per què WATCHLIST i no ACCEPTED**:
- EV amb liquidació modest (+5.6$/t)
- 5 anys positius / 5 negatius (amb liq simulada)
- Sol no justifica BUILD
- Potencialment útil dins portfolio combinat o amb capital > 1.000$

**Acció**: validar com a component d'un portfolio multi-setup (T6+)

**Scripts**: mc_walkforward_capitulation.py, stress_test_capitulation.py, leverage_recalibration.py

---

### 2. Markov HMM Regime (REJECTED)

**Tesi**: HMM detecta règim (bull/lateral/bear) → comprar dips (RL|RL) en règim bull.

**Per què REJECTED**:
- HMM amb features curtes: bon IS, falla 2026 (classifica bull enmig de crash -43%)
- HMM amb features macro: arregla 2026 però perd l'edge IS/OOS
- No es pot simultàniament detectar règim i generar edge

**Scripts**: eth_scalp_markov_v3.py, eth_scalp_markov_v4.py

---

### 3. Markov pur trigrams (REJECTED)

**Tesi**: Seqüències de 3 candles prediuen la següent amb probabilitat.

**Per què REJECTED**:
- 12-14 estats → 1728+ trigrams → N per trigram massa baix
- 4-6 estats → massa genèric, sense edge sobre base rate
- IS bo (overfitting), OOS negatiu sempre

**Scripts**: eth_scalp_markov.py, eth_scalp_markov_v2.py

---

---

### 0. capitulation_d1 (ACCEPTED_D1_ASSET — T7 PAPER PROBE ACTIU)

**Tesi**: Crash extrem D1 (body<-2%, close<BB_lower) → rebot el dia T+1.
Setup congelat (gate T6e, 8/8 criteris MSFT).

**Validació MSFT**:
- WR 78%, PF 3.46, EV +12.7$/trade @20x, liq 0%, MAE med 0.75%
- MC Shuffle: 100%, WF: 10/12 (83% anys positius)
- Capital simulat: 250$ → 772$ en 12 anys (CAGR ~10% fixed, ~25% compounding)

**Univers**:
- MSFT (primari, ACCEPTED) | NVDA (WATCHLIST) | QQQ (WATCHLIST)
- Tots els altres assets testats: REJECTED (T6d/T6f/T6g)

**Scripts**: `lab/studies/t6d_leverage_sweep_d1.py`, `lab/studies/t6e_*`, etc.
**Codi prod**: `packages/strategy/capitulation_d1.py`
**Runbook**: `docs/PAPER_PROBE_RUNBOOK.md`

---

## Candidats prioritaris per la següent fase

| Prioritat | Què fer | Per què |
|-----------|---------|---------|
| **1** | Normalitzar `eth_scalp_backtest.py` com a harness de validació reutilitzable | Ja fa multi-asset, compounding, paper mode. Cal parametritzar per qualsevol setup |
| **2** | Explorar nous setups amb el harness: altres famílies (momentum, breakout), altres assets (non-crypto D1), portfolio combinat | El capitulation sol és WATCHLIST; cal més peces |
| **3** | Actualitzar `eth_capitulation_scalp.md` amb resultats T1 | Documentació obsoleta (diu 100x) |

---

## Conclusions T4

1. **El LAB té 1 setup real** (Capitulation Scalp) i 2 línies d'investigació mortes (Markov)
2. **L'evolució ha estat sana**: Markov → HMM → Indicadors simples → Setup validat
3. **El setup és WATCHLIST**, no ACCEPTED: edge real però EV insuficient sol
4. **Pròxim pas**: construir el harness de validació unificat (T5) i explorar nous setups per trobar un portfolio que justifiqui BUILD
