# HARNESS_VALIDACIO.md — Guia del harness de validació

## Què és

Pipeline unificat per validar qualsevol setup del LAB. Garanteix que tots els setups passen pel mateix procés i produeixen mètriques comparables.

## Ús

```python
from lab.contracts.models import SetupSpec
from lab.harness.core import TradeRecord
from lab.harness.runner import HarnessConfig, validate_setup, save_artifact, print_summary

# 1. Definir el setup
spec = SetupSpec(name="my_setup", ...)

# 2. Generar trades (cada setup implementa la seva lògica)
trades: list[TradeRecord] = generate_my_signals(data)

# 3. Validar
config = HarnessConfig(leverage_deployable=20)
result, artifact = validate_setup(spec, trades, all_candle_moves, config)

# 4. Mostrar i guardar
print_summary(result, artifact)
save_artifact(artifact, spec.name)
```

## Pipeline (7 passes)

| Pas | Què fa | Output |
|-----|--------|--------|
| 1 | Backtest baseline (sense liquidació) | WR, PF, EV teòric |
| 2 | Backtest deployable (amb liq + paper mode + compounding) | WR, PF, EV real, capital |
| 3 | MFE/MAE | Distribució favorable/adversa |
| 4 | Liquidació per leverage (5 leverages) | liq_rate per cada lev |
| 5 | Monte Carlo (shuffle + random entry) | % sims profitables, edge vs random |
| 6 | Walk-forward (expanding + rolling 3y) | anys positius |
| 7 | Classificació automàtica | ACCEPTED / WATCHLIST / REJECTED |

## Dues capes de resultat

| Capa | Liquidació | Fees | Compounding | Paper mode | Per a què |
|------|------------|------|-------------|------------|-----------|
| **Baseline** | No | Sí | No | No | Edge teòric |
| **Deployable** | Sí | Sí | Sí | Sí | Decisió real |

## Criteris de classificació

### ACCEPTED
- N ≥ 80, trades/any ≥ 12
- PF ≥ 1.30, EV deployable ≥ +8$/trade
- Liq rate ≤ 15% al leverage operatiu
- WR ≥ 55%

### WATCHLIST
- MC PASS però algun criteri ACCEPTED no es compleix
- Edge real, potencialment útil en portfolio

### REJECTED
- MC shuffle < 90% sims profitables
- O WF expanding < 50% anys positius

## Artifacts

- `lab/out/{setup_name}_validation.json` — resultat complet serialitzat
- Terminal: resum llegible amb baseline, deployable, MC, WF, yearly

## Configuració

```python
HarnessConfig(
    nominal_baseline=4000.0,    # nominal fix per baseline
    fee=3.36,                   # fee per trade
    init_capital=250.0,         # capital inicial
    col_pct=0.20,               # 20% del capital per trade
    col_min=15.0, col_max=60.0, # límits col·lateral
    leverages_to_test=(10, 15, 20, 30, 50),
    leverage_deployable=20,     # leverage per mètriques deployable
    paper_threshold=2,          # 2 losses → paper mode
    mc_n_shuffle=10000,
    mc_n_random=5000,
    wf_train_window=3,
)
```

## Smoke test

```bash
python3 lab/harness/smoke_capitulation.py --cache /tmp/crypto_1h_cache.pkl
```

Verifica que Capitulation Scalp 1H surt WATCHLIST (coherent amb catàleg T4).
