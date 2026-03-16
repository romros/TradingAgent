# Resum per ChatGPT — Cap de Projecte TradingAgent

Actualitzat: 2026-03-16 (post-T6c, 3 cicles d'exploració completats)

---

## ESTAT: LAB — 2 WATCHLIST trobats, decisió pendent

**Repo:** github.com/romros/TradingAgent (12 commits a main)

### Tasques tancades (T1-T6c)

| Tasca | Resultat |
|-------|----------|
| T1 | Leverage 20x (100x descartada) |
| T2 | Gate de producció establert |
| T3 | Contracte canònic LAB |
| T4 | Inventari: 1 WATCHLIST crypto, 2 REJECTED Markov |
| T5 | Harness validació (7 passes, smoke PASS) |
| T6 | Crypto 1H: 5 REJECTED, 1 WATCHLIST N=11 |
| T6b | **Crypto 4H: 6/6 REJECTED** (MAE massa alta per leverage) |
| T6c | **Equitats D1: 1 WATCHLIST (N=288)** Nasdaq/NVDA/MSFT prometedors |

---

## Exploració completada: 18 setups en 3 terrenys

### T6 — Crypto 1H (el que ja teníem)
- Capitulation Scalp: WATCHLIST (WR 68%, PF 2.94, EV deploy +4$/t amb liq 20x)
- Breakout, sweep, hammer, pullback: tots MC 0%, REJECTED
- **Insight**: TA clàssic no funciona a crypto 1H amb fees Ostium

### T6b — Crypto 4H (pivot 1)
- 6/6 REJECTED
- Capitulation: baseline WR 64% PF 1.94, **però liq 38.6% a 20x** → EV negatiu
- Breakout/momentum: edge teòric massa petit per fees
- **Insight**: crypto 4H massa volàtil per apalancar (MAE mediana 3-5%)

### T6c — Equitats D1 (pivot 2) ← TROBADA

| Setup | N | WR | PF | EV deploy | Liq 20x | Status |
|-------|---|-----|-----|-----------|---------|--------|
| **capitulation_d1 COMBINED** | **288** | **60%** | **2.59** | **+3.3$** | **8.0%** | **WATCHLIST** |

**Per asset individual:**

| Asset | N | WR | PF | EV deploy | Liq 20x | MC | WF |
|-------|---|-----|-----|-----------|---------|-----|-----|
| **Nasdaq** | 33 | **73%** | **17.1** | **+20.7$** | **0%** | 100% | 7/7 |
| **MSFT** | 27 | **74%** | **6.2** | **+16.5$** | **0%** | 100% | 7/9 |
| **NVDA** | 54 | **67%** | **3.8** | **+9.7$** | **5.6%** | 100% | 8/10 |
| AAPL | 30 | 50% | 2.3 | -2.4$ | 3.3% | 100% | 4/9 |

**Per què equitats D1 funciona i crypto 4H no?**
- MAE mediana equitats: 1.2-2% vs crypto 3-5%
- Liq a 20x: 0-8% vs 22-38%
- Moves diaris 2-3% cobreixen fees (5.38$) millor
- WF: 9/10 anys positius combinat

---

## ON SOM ARA

### El que tenim (2 WATCHLIST, 2 famílies/terrenys)

1. **Capitulation Scalp 1H crypto** (ETH, BTC, SOL)
   - WR 68%, PF 2.94, EV deploy +4$/t, liq 14%
   - 24/7 operació, ~18 trades/any
   - Events extrems (crashes -3%+)

2. **Capitulation D1 equitats** (Nasdaq, NVDA, MSFT)
   - WR 60%, PF 2.59, EV deploy +3.3$/t combined, liq 8%
   - Market hours, ~29 trades/any combined
   - Nasdaq individual: WR 73%, EV +20.7$/t (!), liq 0%

### Portfolio potencial
- Crypto 24/7 (senyals extrems, poc freqüents)
- Equitats market hours (més freqüent, menys liquidació)
- **Complementaris**: crypto funciona en crashes, equitats en dips intraday

### El que NO tenim (per a ACCEPTED)
- Cap setup arriba als criteris d'ACCEPTED (EV≥8$, PF≥1.30, N≥120 en deployable)
- Individualmente Nasdaq/NVDA són brutals però N=33/54 — poc per estadística robusta
- El combined equitats (N=288) té EV deploy +3.3$ < 8$ threshold

---

## QUÈ NECESSITO DE TU

Has dit "A amb límit de 2 cicles, C si no surt res". T6b i T6c són els 2 cicles. Ara:

1. **T6c ha canviat el panorama**: equitats D1 mostra edge real amb liq molt baixa. Canvia la teva recomanació?

2. **El criteri d'ACCEPTED (EV≥8$ deploy) és massa dur per equitats?** Amb lev 20x i fees 5.38$, el move net per trade és petit. Però amb lev 10-15x (liq 0-3%), l'EV deployable pugés significativament perquè no es perden trades per liquidació.

3. **Decisió**: amb 2 WATCHLIST de 2 terrenys (crypto + equitats), autoritzem BUILD? O seguim LAB per intentar pujar-les a ACCEPTED?

4. **Alternativa pragmàtica**: construir el bot amb 2 WATCHLIST com a infra reutilitzable, operar en paper 4 setmanes, i usar la paper experience per decidir el go/no-go real?

Respon en català. Sigues directe.
