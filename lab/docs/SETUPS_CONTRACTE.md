# SETUPS_CONTRACTE.md — Contracte canònic del LAB

## Què és un setup

Un **setup** és una combinació de condicions de mercat que, quan es donen, generen una oportunitat d'entrada amb un biaix estadístic mesurable. Un setup NO és una estratègia completa — és la peça d'entrada que alimenta la cadena `Strategy → Risk → Execution`.

## Marc temporal

| Concepte | Valor per defecte | Significat |
|----------|-------------------|------------|
| `tf_context` | **4H** | Finestra de context per indicadors i scoring. Quantes hores de mercat mirem per decidir |
| `tf_execution` | **1H** | Finestra d'execució. Entry a l'open, exit al close (hold 1H) |

Un setup evalua 4H de context per predir si la **propera candle 1H** serà favorable.

## Les 3 estructures

### 1. SetupSpec — Descripció

Defineix **QUÈ** és el setup (declaratiu, sense codi d'execució):
- Nom, família, tesi (per què funciona)
- Assets, timeframes
- Condicions d'entrada (text + programàtic)
- Sortida baseline
- Features/indicadors usats
- Scoring

### 2. SetupValidationResult — Validació

Mesura **COM** funciona el setup amb dades històriques:
- WR, PF, EV/trade
- MFE/MAE (distribució del moviment favorable/advers)
- Liquidació per leverage (10x, 15x, 20x, 30x, 50x)
- Monte Carlo (shuffle, random entry, param perturbation)
- Walk-forward (expanding + rolling)
- Yearly breakdown
- **Status**: `CANDIDATE → ACCEPTED | WATCHLIST | REJECTED`

### 3. OpportunityEstimate — Estimació en temps real

Genera **QUÈ ESPERAR** quan el setup s'activa:
- MFE/MAE esperat (4H i 1H)
- Risc de liquidació per leverage
- Score, qualitat, confiança
- Tier (LOW/MID/HIGH)

Aquesta estructura alimenta:
- **Agent de risc**: decideix si entrar, amb quin leverage i col·lateral
- **Agent d'exit**: decideix quan tancar (TP dinàmic, SL adaptatiu)

## Cicle de vida d'un setup

```
CANDIDATE
    │
    ├── Backtest baseline → mètriques core (WR, PF, EV)
    ├── Liquidació simulada → liq_rate per leverage
    ├── Monte Carlo → edge real vs random
    ├── Walk-Forward → estabilitat temporal
    │
    ├── Si tot PASS i cas econòmic suficient → ACCEPTED
    ├── Si edge real però cas econòmic insuficient → WATCHLIST
    └── Si no passa MC o WF → REJECTED
```

## Criteris de classificació

### ACCEPTED
- MC Shuffle: ≥90% sims profitables
- MC Random Entry: WR real > P95 random
- MC Param Perturbation: ≥80% variants profitables
- WF Expanding: ≥70% anys positius
- Liq rate ≤20% al leverage operatiu
- EV/trade > 0 amb liquidació simulada

### WATCHLIST
- Edge real (MC Random > P95) però:
  - EV/trade massa baix per operar sol
  - O massa pocs trades/any
  - O massa anys negatius
  - Potencialment útil dins d'un portfolio combinat

### REJECTED
- MC Random ≤ P95 (no hi ha edge)
- O MC Param Perturbation < 50% (overfitting)
- O WF < 50% anys positius

## Mètriques obligatòries per validació

| Mètrica | Obligatòria | Per què |
|---------|-------------|---------|
| sample_size | Sí | N mínim per fiabilitat |
| win_rate | Sí | Baseline |
| profit_factor | Sí | Ratio guany/pèrdua |
| ev_per_trade | Sí | Amb fees + liquidació |
| mfe_mean/median | Sí | Per agent d'exit |
| mae_mean/median | Sí | Per agent de risc |
| liq_rates (≥3 leverages) | Sí | Per sizing |
| mc_shuffle | Sí | Validació distribució |
| mc_random_edge | Sí | Validació edge |
| mc_param_perturb | Sí | Robustesa paràmetres |
| wf_expanding | Sí | Estabilitat temporal |
| yearly_breakdown | Sí | Per identificar anys febles |

## Exemple: Capitulation Scalp 1H

Veure `lab/contracts/examples/capitulation_scalp_example.py` per un exemple complet omplert amb dades reals.

## Relació amb l'arquitectura productiva

Quan el projecte passi a BUILD:
- `SetupSpec` → alimenta `packages/strategy/capitulation_scalp.py`
- `OpportunityEstimate` → és el `Signal` que retorna `strategy.evaluate()`
- `SetupValidationResult` → evidència per decidir leverage, sizing i mode al `Risk Manager`

El contracte del LAB és el **subsòl** de l'arquitectura productiva definida a AGENTS_ARQUITECTURA.md.
