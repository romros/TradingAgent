# LAB_INVENTARI.md — Inventari complet del laboratori

Actualitzat: 2026-03-16 (T4)

---

## lab/explore/ — Exploració (scripts d'investigació)

| Fitxer | Categoria | Família | Resum | Estat | Acció |
|--------|-----------|---------|-------|-------|-------|
| `eth_scalp_markov.py` | explore | pattern | Cadenes de Markov sobre candles 4H ETH. 12 estats, trigrams. Resultat: overfitting (IS +15$/t, OOS -14$/t) | DISCARDED | archive |
| `eth_scalp_markov_v2.py` | explore | pattern | Iteració 2: menys estats, IC 95%, walk-forward. Més rigorós però cap edge OOS robust | DISCARDED | archive |
| `eth_scalp_markov_v3.py` | explore | pattern | HMM regime detection + bigrams. R\*\|RL en BULL dona edge OOS. Però HMM falla al 2026 (no detecta bear) | DISCARDED | archive |
| `eth_scalp_markov_v4.py` | explore | pattern | Walk-forward HMM, variacions del senyal, RSI/BB. BB<lower + R\*\|RL millora. Precursor del setup capitulation | WATCHLIST | normalize |
| `eth_scalp_final.py` | explore→study | capitulation | Anàlisi final del setup capitulation (single-asset ETH). Scoring, MFE/MAE per tier, hores | CANDIDATE | normalize |
| `eth_scalp_backtest.py` | study | capitulation | Backtest multi-asset complet amb compounding, paper mode, 1 pos max. Base del MC/WF | CANDIDATE | normalize |

### Resum explore/

- **Evolució clara**: Markov pur (v1) → HMM (v3) → Indicadors simples BB+drop (v4) → Capitulation setup (final)
- La cadena de Markov va ser un dead-end (overfitting)
- L'HMM va revelar que el **règim importa** però és difícil de detectar en temps real
- El que funciona: condicions simples (body, BB, drop, hora) — no cal model complex

---

## lab/strategies/ — Documentació d'estratègies

| Fitxer | Categoria | Resum | Estat | Acció |
|--------|-----------|-------|-------|-------|
| `eth_capitulation_scalp.md` | doc | Regles operatives del setup capitulation. **ATENCIÓ**: encara diu leverage 100x (pre-T1) | OBSOLET | actualitzar amb resultats T1 (leverage 20x) |
| `prompt_chatgpt_trading_bot.md` | doc | Prompt per ChatGPT com a cap de projecte. Arquitectura completa del bot | VIGENT | mantenir |
| `resum_chatgpt_cap_projecte.md` | doc | Resum actualitzat post-T1 per ChatGPT | VIGENT | mantenir |

---

## lab/studies/ — Estudis de validació

| Fitxer | Categoria | Resum | Estat | Acció |
|--------|-----------|-------|-------|-------|
| `mc_walkforward_capitulation.py` | study | MC (shuffle, random entry, param perturb) + WF (expanding, rolling). **PASS 3/3** | ACCEPTED_SEED | mantenir |
| `stress_test_capitulation.py` | study | Stress test: worst streak, Kelly, DD, liquidació, fees. Va revelar lev 100x inviable | ACCEPTED_SEED | mantenir |
| `leverage_recalibration.py` | study | T1: backtest amb liquidació simulada per leverages 10-100x. Decisió: 20x | ACCEPTED_SEED | mantenir |

---

## lab/contracts/ — Contracte canònic (T3)

| Fitxer | Categoria | Resum | Estat |
|--------|-----------|-------|-------|
| `models.py` | infra | SetupSpec, SetupValidationResult, OpportunityEstimate | VIGENT |
| `examples/capitulation_scalp_example.py` | infra | Exemple complet omplert (status: WATCHLIST) | VIGENT |

---

## lab/docs/ — Documentació del LAB

| Fitxer | Resum |
|--------|-------|
| `SETUPS_CONTRACTE.md` | Contracte canònic, cicle de vida, criteris (T3) |
| `LAB_INVENTARI.md` | Aquest fitxer |
| `SETUPS_CATALOG.md` | Catàleg de setups orientat a decisió |

---

## lab/out/ — Artifacts de sortida

| Fitxer | Resum |
|--------|-------|
| `leverage_recalibration.json` | Artifact T1: resultats per leverage |
