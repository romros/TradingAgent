# Resum per ChatGPT — Cap de Projecte TradingAgent

Actualitzat: 2026-03-16 (post-T6d, leverage sweep complet)

---

## ESTAT: LAB — 4 WATCHLIST, 0 ACCEPTED, decisió pendent

**Repo:** github.com/romros/TradingAgent (commits a main)

### Tasques tancades (T1-T6d)

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
| T6d | **Leverage sweep D1: MSFT estrella** (WR 78%, EV +12.7$@20x, liq 0%) |

---

## Exploració completada: 4 terrenys, 28+ setups

### T6 — Crypto 1H
- Capitulation Scalp: WATCHLIST (WR 68%, PF 2.94, EV deploy +4$/t amb liq 20x)
- Breakout, sweep, hammer, pullback: tots MC 0%, REJECTED
- **Insight**: TA clàssic no funciona a crypto 1H amb fees Ostium

### T6b — Crypto 4H (pivot 1)
- 6/6 REJECTED
- **Insight**: crypto 4H massa volàtil per apalancar (MAE mediana 3-5%)

### T6c — Equitats D1 (pivot 2)
- capitulation_d1 COMBINED: WATCHLIST (N=288, WR 60%, PF 2.59)
- Nasdaq individual: WR 73%, EV +20.7$/t (!), liq 0%, MC 100%, WF 7/7

### T6d — Leverage sweep D1 complet (10 assets × 6 leverages)

| Asset | N | WR | EV@20x | Liq@20x | BestLev | EV@best | WF | Status |
|-------|---|-----|--------|---------|---------|---------|-----|--------|
| **MSFT** | **41** | **78%** | **+12.7$** | **0%** | 30x | +13.7$ | 10/12 | **WATCHLIST** |
| **NVDA** | **68** | **63%** | **+6.0$** | **4.4%** | 20x | +6.0$ | 11/13 | **WATCHLIST** |
| **QQQ** | **40** | **62%** | **+3.6$** | **2.5%** | 20x | +3.6$ | 7/8 | **WATCHLIST** |
| SPY | 23 | 74% | +3.3$ | 4.3% | 30x | +11.8$ | 7/8 | REJECTED (N<40) |
| AAPL | 41 | 51% | +1.2$ | 2.4% | — | — | 6/12 | REJECTED |
| AMZN | 54 | 56% | -2.5$ | 3.7% | — | — | 9/12 | REJECTED |
| META | 60 | 62% | -2.9$ | 6.7% | — | — | 8/12 | REJECTED |
| GOOGL | 48 | 58% | -3.5$ | 2.1% | — | — | 9/12 | REJECTED |
| TSLA | 87 | 52% | -9.1$ | 18.4% | — | — | 8/13 | REJECTED |
| GLD | 2 | — | — | — | — | — | — | REJECTED (N<20) |

---

## PORTFOLIO COMPLET: 4 WATCHLIST de 2 famílies

### Família 1: Capitulation Scalp 1H crypto (ETH, BTC, SOL)
- WR 68%, PF 2.94, EV deploy +4$/t, liq 14%
- 24/7 operació, ~18 trades/any (3 assets)
- Events extrems (crashes -3%+)

### Família 2: Capitulation D1 equitats (MSFT, NVDA, QQQ)
- **MSFT**: WR 78%, EV +12.7$@20x, liq 0%, WF 10/12 — el millor asset individual
- **NVDA**: WR 63%, EV +6.0$@20x, liq 4.4%, WF 11/13
- **QQQ**: WR 62%, EV +3.6$@20x, liq 2.5%, WF 7/8
- Market hours, ~12 trades/any (3 assets combinats)
- MAE mediana 0.75-1.5% → tolerant a leverage fins 20-25x

---

## PER QUÈ NO TENIM ACCEPTED

**Gate ACCEPTED**: EV≥8$/t deployable + N≥120 + PF≥1.30 + MC≥90% + WF≥60%

**Bloqueig estructural del D1**: ~3-4 events/any/asset → N=40-68 en 12 anys
- Per MSFT: EV +12.7$ (≥8$ ✓) però N=41 (< 120 ✗)
- El gate N≥120 requereix 35+ anys de dades D1 — impossible
- Combined 3 equitats: N≈149 (≥120 ✓) però EV combinat ~7$ (< 8$ ✗)

**Gap de 1$**: la combinació equitats té EV ~7$ vs threshold 8$. Molt a prop.

---

## OPCIONS PER A LA DECISIÓ

### Opció A: Paper probe 4 setmanes (recomanada)
- BUILD infra mínima: detector de senyal + notificació + tracking manual
- Operació paper (0$ real) durant 4 setmanes
- Acumular evidència real: slippage, fills, timing
- Al final: go/no-go real basat en paper + LAB combinat

### Opció B: Continuar LAB
- Buscar assets D1 addicionals per augmentar N combined
- SPY: N=23, EV@30x=+11.8$ → si s'afegeix, combined N≈172, EV potser ≥8$
- Però: SPY i QQQ estan molt correlacionats (Nasdaq vs S&P 500)
- Riscos: seguim acumulant evidence sense mai arribar a ACCEPTED

### Opció C: Relaxar gate per D1
- Reconèixer que N≥120 és impossible per D1 de baixa freqüència
- Gate alternatiu D1: N≥60, EV≥8$, PF≥1.30, WF≥70%
- MSFT i el combined 3 assets quasi passen (o passen amb N combinat)
- Permet BUILD autoritzat mantenint rigor estadístic adaptat al TF

---

## QUÈ NECESSITO DE TU

Hem completat T6d. Ara:

1. **T6d canvia el panorama?** MSFT mostra WR 78%, EV +12.7$, liq 0%, WF 10/12.
   És l'asset individual més fort que hem vist. Però N=41.

2. **El gate N≥120 és raonable per D1?** Matemàticament impossible per un sol asset
   en dades disponibles. El combined 3 assets (N≈149) té EV ~7$ — a 1$ del threshold.

3. **Decisió final**: Amb 4 WATCHLIST de 2 famílies (crypto + equitats), i MSFT
   quasi-ACCEPTED per EV però no per N:
   - A) Paper probe 4 setmanes + BUILD infra mínima
   - B) LAB continua: afegir SPY al combined (potser ≥8$ EV)
   - C) Gate adaptat per D1 → BUILD autoritzat

4. **Combinació crypto + equitats**: pot ser portafoli complementari?
   - Crypto funciona en crashes extrems 24/7
   - Equitats funcionen en dips D1 market hours
   - EV total portfolio: +4$ (crypto) + ~7$ (equitats) = ~11$/t weighted

Respon en català. Sigues directe.
