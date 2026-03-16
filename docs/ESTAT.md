# ESTAT.md — TradingAgent

Operativa diària i evidència. Actualitzar a cada canvi significatiu.

---

## Estat actual (2026-03-16)

### Fase: SETUP

- [x] Estructura de directoris creada
- [x] CLAUDE.md, AGENTS_ARQUITECTURA.md, README.md
- [x] Lab amb estratègies importades de SQRunner
- [x] Monte Carlo validation de Capitulation Scalp 1H — PASS (3/3)
- [x] Walk-forward validation — PASS (7/9 expanding, 5/7 rolling)
- [x] Stress test — ALERTA: lev 100x = 61% liquidacions. Recomanat lev 20-30x
- [ ] Refer backtest amb liquidació simulada (leverage recalibrat)
- [ ] MVP: packages/shared/models.py
- [ ] MVP: packages/market/indicators.py
- [ ] MVP: packages/strategy/capitulation_scalp.py
- [ ] MVP: packages/brokerage/client.py
- [ ] MVP: packages/execution/{paper,live}.py
- [ ] MVP: packages/risk/manager.py
- [ ] MVP: packages/portfolio/{db,tracker}.py
- [ ] MVP: packages/runtime/engine.py
- [ ] MVP: apps/agent/{app,routes}.py
- [ ] Tests unitaris
- [ ] Docker compose + deploy
- [ ] Paper testing 2-4 setmanes
- [ ] Go live

### Estratègia activa

**Capitulation Scalp 1H** — LONG after crash extrem crypto
- Assets: ETH, BTC, SOL
- TF: 1H
- Backtest: WR 68%, PF 2.5, 361 trades (3 assets), +18.335$ (8.6 anys)
- MC Shuffle: PASS (100% sims profitables)
- MC Random Entry: PASS (edge +15-35pp vs random, tots > P95)
- MC Param Perturb: PASS (50/50 variants profitables, WR min 63%)
- WF Expanding: 7/9 anys positius (2023 -155$, 2024 -206$ — N baix)
- WF Rolling 3y: 5/7 anys positius
- Script: `lab/studies/mc_walkforward_capitulation.py`

### ALERTA: Leverage 100x no viable

El stress test ha revelat que **el 61% dels trades serien liquidats amb lev 100x** (MAE mediana 1.50%, liq threshold 1%). Cal refer el backtest amb liquidació simulada a lev 20-30x per trobar l'equilibri rendiment/supervivència.

### Pròxim pas

1. Refer backtest amb liquidació simulada (lev 20x, 30x, 50x)
2. Implementar MVP amb leverage recalibrat

---

## Historial

| Data | Acció |
|------|-------|
| 2026-03-16 | Projecte creat. Estructura, MDs, lab importat de SQRunner |
| 2026-03-16 | MC+WF PASS. Shuffle 100%, Random Entry edge +15-35pp, Param Perturb 50/50 |
| 2026-03-16 | STRESS TEST: lev 100x = 61% liquidacions! Kelly=47%, sizing 20% OK. Recomanat lev 20-30x |
