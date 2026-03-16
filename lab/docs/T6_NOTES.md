# T6 NOTES — Resultats exploració nous setups

Data: 2026-03-16

## Resum final (T6 + T6b + T6c)

3 cicles d'exploració completats:

| Cicle | Terreny | Setups | ACCEPTED | WATCHLIST | REJECTED |
|-------|---------|--------|----------|-----------|----------|
| T6 | Crypto 1H | 6 | 0 | 1 (N=11) | 5 |
| T6b | Crypto 4H | 6 | 0 | 0 | 6 |
| T6c | Equitats D1 | 6 | 0 | **1 (N=288)** | 5 |
| **Total** | | **18** | **0** | **2** | **16** |

---

## T6 — Crypto 1H (6 setups)

| Setup | Family | N | WR_b | PF_b | MC% | Status |
|-------|--------|---|------|------|-----|--------|
| capitulation_scalp_1h (ref) | capitulation | 361 | 68% | 2.94 | 100% | WATCHLIST |
| bb_squeeze_breakout | breakout | 1105 | 38% | 0.77 | 0% | REJECTED |
| atr_low_big_candle | breakout | 137 | 37% | 0.77 | 0% | REJECTED |
| sweep_reclaim | mean_reversion | 11365 | 43% | 0.79 | 0% | REJECTED |
| hammer | pattern | 9307 | 41% | 0.67 | 0% | REJECTED |
| trend_rsi_dip | momentum | 11 | 73% | 2.86 | 100% | WATCHLIST (N insuficient) |
| pullback_ema20 | momentum | 11967 | 42% | 0.86 | 0% | REJECTED |

**Insight**: patrons clàssics TA no funcionen a crypto 1H amb fees Ostium.

---

## T6b — Crypto 4H (6 setups)

| Setup | Family | N | WR_b | PF_b | EV_d | Liq 20x | Status |
|-------|--------|---|------|------|------|---------|--------|
| capitulation_4h_extreme | capitulation | 197 | 64% | 1.94 | -3.9$ | 38.6% | REJECTED |
| capitulation_4h_mild | capitulation | 556 | 56% | 1.35 | -2.6$ | 22.3% | REJECTED |
| bb_squeeze_breakout_4h | breakout | 1520 | 51% | 1.40 | -1.9$ | 0.7% | REJECTED |
| atr_expansion_4h | breakout | 71 | 58% | 2.30 | +0.8$ | 1.4% | REJECTED |
| trend_rsi_dip_4h | momentum | 0 | — | — | — | — | REJECTED |
| pullback_ema20_4h | momentum | 2653 | 51% | 1.16 | -3.0$ | 3.2% | REJECTED |

**Insight**: crypto 4H massa volàtil per apalancar (MAE 3-5% >> liq threshold 5% a 20x).

---

## T6c — Equitats D1 (6 setups × 8 assets) ← TROBADA IMPORTANT

| Setup | N | WR_b | PF_b | EV_d | Liq 20x | Best asset | Status |
|-------|---|------|------|------|---------|------------|--------|
| **capitulation_d1** | **288** | **60%** | **2.59** | **+3.3$** | **8.0%** | **Nasdaq** | **WATCHLIST** |
| cap_d1_ema200 | 107 | 59% | 2.15 | -2.1$ | 8.4% | MSFT | REJECTED |
| breakout_squeeze_d1 | 102 | 60% | 1.52 | -3.9$ | 0.0% | AMZN | REJECTED |
| trend_rsi_dip_d1 | 0 | — | — | — | — | — | REJECTED |
| pullback_ema20_d1 | 851 | 51% | 1.03 | -5.9$ | 1.4% | — | REJECTED |
| big_red_bounce_d1 | 509 | 57% | 1.44 | -3.8$ | 10.2% | Nasdaq | REJECTED |

### Assets individuals prometedors (capitulation_d1):

| Asset | N | WR | PF | EV deploy | Liq 20x | MC | WF |
|-------|---|-----|-----|-----------|---------|-----|-----|
| **Nasdaq** | 33 | 73% | 17.1 | **+20.7$** | 0% | 100% | 7/7 |
| **MSFT** | 27 | 74% | 6.2 | **+16.5$** | 0% | 100% | 7/9 |
| **NVDA** | 54 | 67% | 3.8 | **+9.7$** | 5.6% | 100% | 8/10 |
| AAPL | 30 | 50% | 2.3 | -2.4$ | 3.3% | 100% | 4/9 |
| META | 44 | 61% | 1.4 | -4.5$ | 9.1% | 100% | 5/9 |

**Insight**: equitats D1 amb capitulation → liq rate molt més baixa (0-8% vs 22-38% crypto).
El move diari (2-3%) cobreix millor les fees (5.38$) i la MAE és més manejable.

---

## Conclusions generals

1. **L'únic setup que funciona en múltiples terrenys**: Capitulation (mean reversion extrema)
2. **Crypto 1H/4H**: massa volàtil per leverage + fees fixes massa altes vs move
3. **Equitats D1**: millor ratio move/fee, menys liquidacions, edge consistents
4. **Patrons TA clàssics**: no funcionen amb fees d'Ostium en cap terreny
5. **El millor terreny descobert**: equitats D1, especialment Nasdaq, NVDA, MSFT

## Candidats per T7

1. **Capitulation Scalp 1H crypto** — WATCHLIST, EV modest però l'únic crypto viable
2. **Capitulation D1 equitats** — WATCHLIST, Nasdaq/NVDA/MSFT prometedors
3. **Potencial portfolio**: crypto (24/7, events extrems) + equitats D1 (market hours, crashes)
