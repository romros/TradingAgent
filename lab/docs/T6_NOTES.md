# T6 NOTES — Resultats exploració nous setups

Data: 2026-03-16

## Resum

6 hipòtesis en 3 famílies, totes pel harness T5. **4 REJECTED, 1 WATCHLIST (N=11), 1 referència WATCHLIST.**

El Capitulation Scalp continua sent l'únic setup amb edge real en crypto 1H.

## Taula comparativa

| Setup | Family | N | WR_b | PF_b | EV_b | MC% | Edge | WF | Status |
|-------|--------|---|------|------|------|-----|------|-----|--------|
| capitulation_scalp_1h (ref) | capitulation | 361 | 68% | 2.94 | +50.8$ | 100% | +24.6pp | 8/10 | WATCHLIST |
| f1a_bb_squeeze_breakout | breakout | 1105 | 38% | 0.77 | -2.7$ | 0% | -5.6pp | 3/10 | REJECTED |
| f1b_atr_low_big_candle | breakout | 137 | 37% | 0.77 | -3.6$ | 0% | -6.0pp | 4/10 | REJECTED |
| f2a_sweep_reclaim | mean_reversion | 11365 | 43% | 0.79 | -2.8$ | 0% | -0.3pp | 1/10 | REJECTED |
| f2b_hammer | pattern | 9307 | 41% | 0.67 | -3.5$ | 0% | -2.6pp | 1/10 | REJECTED |
| f3a_trend_rsi_dip | momentum | 11 | 73% | 2.86 | +4.9$ | 100% | +29.7pp | 3/4 | WATCHLIST |
| f3b_pullback_ema20 | momentum | 11967 | 42% | 0.86 | -2.0$ | 0% | -0.8pp | 1/10 | REJECTED |

## Insights

1. Patrons clàssics TA (breakout, hammer, pullback) NO funcionen a crypto 1H amb fees d'Ostium
2. WR baseline 37-43% = pitjor que random (fees destrueixen l'edge teòric)
3. Únicament condicions extremes (capitulation, RSI dip en tendència forta) mostren edge
4. Trend RSI dip té edge (MC 100%, +29.7pp) però N=11 és insuficient per validar

## Candidats per T7

1. **Capitulation Scalp** — únic WATCHLIST amb N suficient (361)
2. **Trend RSI dip** — WATCHLIST però N=11, necessita més historial o TF diferent

## Recomanació

El LAB crypto 1H s'ha esgotat amb 1 sol setup viable. Opcions:
- Explorar TF més llargs (4H, D1) per trend RSI dip (més N)
- Explorar assets no-crypto (equitats D1 — ja validat parcialment a SQRunner)
- Acceptar Capitulation sol i construir el bot com a infra reutilitzable
