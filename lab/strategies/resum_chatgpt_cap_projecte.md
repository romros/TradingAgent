# Resum per ChatGPT — Cap de Projecte TradingAgent

Actualitzat: 2026-03-16 (post-T5)

---

## ESTAT: LAB — 5 tasques tancades, harness funcional

**Repo:** github.com/romros/TradingAgent (8 commits a main)

### Tasques tancades

| Tasca | Resultat |
|-------|----------|
| **T1** | Leverage recalibrat: 20x (100x descartada, 61% liquidacions) |
| **T2** | Docs alineats, gate de producció establert (§9) |
| **T3** | Contracte canònic: SetupSpec, ValidationResult, OpportunityEstimate |
| **T4** | Inventari: 1 WATCHLIST (Capitulation), 2 REJECTED (Markov) |
| **T5** | Harness de validació: pipeline 7 passes, smoke PASS |

### Harness (T5) — com funciona

Pipeline unificat que valida qualsevol setup en 7 passes:

```
1. Backtest baseline (sense liquidació) → edge teòric
2. Backtest deployable (amb liq + paper + compounding) → edge real
3. MFE/MAE → distribució favorable/adversa
4. Liquidació per leverage (5 leverages) → liq_rate
5. Monte Carlo (shuffle + random entry) → significància
6. Walk-forward (expanding + rolling 3y) → estabilitat
7. Classificació automàtica → ACCEPTED / WATCHLIST / REJECTED
```

Dues capes de resultat separades:
- **Baseline**: edge teòric (WR 68%, PF 2.94, EV +50.8$/t)
- **Deployable**: edge real amb liq 20x (WR 57%, PF 1.3, EV +4.0$/t, 250$→1.398$)

Criteris numèrics per ACCEPTED (del ChatGPT PM):
- N≥80, trades/any≥12, PF≥1.30, EV≥+8$, liq≤15%, WR≥55%

### Smoke test Capitulation Scalp → WATCHLIST ✓

El harness confirma Capitulation com WATCHLIST:
- Edge real (MC 100% shuffle, +24.6pp vs random)
- Però EV deployable +4.0$ < 8$ i liq 15.1% > 15%
- Coherent amb catàleg T4

---

## PRÒXIM: T6 — Explorar nous setups

El LAB té 1 sol setup (WATCHLIST). Per justificar BUILD calen mínim 2 ACCEPTED (criteri PM).

### Línies d'investigació recomanades (del ChatGPT PM)

1. **Breakout / continuation post-compressió** — complementari a capitulation
2. **Failed move / reclaim** — MAE potencialment més baixa
3. **Mean reversion fina** — variants amb menys risc de liquidació
4. **Diversificació d'asset** — primer crypto 1H/4H, després D1 equitats

### Gate per autoritzar BUILD (criteri PM)

- Mínim 2 setups ACCEPTED (2 famílies diferents)
- Portfolio agregat: EV≥+10$/t, PF≥1.35, MaxDD≤30%, ≥40 trades/any
- Retorn esperat: ≥300$/any amb 250$ capital
- ≥60% anys positius en validació temporal

---

## QUÈ NECESSITO DE TU (ChatGPT)

T5 tancada. El harness funciona. Ara:

1. **Detalla T6**: quins setups concrets explorar primer? Quins indicadors/condicions provar per breakout i failed move?

2. **Prioritza**: de les 4 línies d'investigació, quina té més probabilitat d'arribar a ACCEPTED amb el marc 4H/1H crypto?

3. **Ajusta el criteri** si cal: amb el harness desplegat, els números que vas donar (EV≥8$, PF≥1.30) són realistes donada la MAE mediana de crypto i les fees d'Ostium?

Respon en català.
