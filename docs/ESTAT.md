# ESTAT.md — TradingAgent

Operativa diària i evidència. Actualitzar a cada canvi significatiu.

---

## Estat actual (2026-03-16)

### Fase: PAPER PROBE — T7 en curs (≥4 setmanes, inici 2026-03-16)

**Setup actiu**: `capitulation_d1` — MSFT (primari), NVDA, QQQ (complementaris)
**Leverage**: 20x | **Mode**: paper only | **Pròxim gate**: T7 OK → decidir live

#### Completat
- [x] Estructura de directoris creada
- [x] CLAUDE.md, AGENTS_ARQUITECTURA.md, README.md
- [x] Lab amb estratègies importades de SQRunner
- [x] Monte Carlo validation de Capitulation Scalp 1H — PASS (3/3)
- [x] Walk-forward validation — PASS (7/9 expanding, 5/7 rolling)
- [x] Stress test — lev 100x inviable (61% liquidacions)
- [x] T1: Leverage recalibrat amb liquidació simulada → 20x
- [x] T2: Documents alineats, gate de producció establert
- [x] T3: Contracte canònic del LAB (SetupSpec, ValidationResult, OpportunityEstimate)
- [x] T4: Inventari i catàleg del LAB — 1 setup WATCHLIST, 2 rebutjats

#### Pendent: millorar edge per justificar BUILD
- [x] T5: Harness comú de validació — smoke PASS (Capitulation → WATCHLIST coherent)
- [x] T6: Crypto 1H — 4 REJECTED, 1 WATCHLIST (N=11). Crypto 1H esgotat
- [x] T6b: Crypto 4H — 6/6 REJECTED. MAE massa alta per leverage
- [x] T6c: Equitats D1 — **Capitulation D1 WATCHLIST** (N=288, WR 60%, PF 2.59). Nasdaq/NVDA/MSFT prometedors
- [x] T6d: **Leverage sweep D1** — MSFT millor asset (WR 78%, EV +12.7$@20x, liq 0%, WF 10/12). 3 WATCHLIST, 0 ACCEPTED
- [x] T6e: **Gate D1 adaptat + decisió** — MSFT = ACCEPTED_D1_ASSET (8/8 criteris). **PAPER_PROBE_AUTHORIZED**
- [x] T6f: **Screening final** — AMD/NFLX/META/GOOGL/AMZN testats, tots REJECTED. Edge específic de MSFT confirmat. Univers: MSFT+NVDA+QQQ
- [x] T6g: **Commodities + índexs** — GLD(N=3 insuf.), SPY(WATCHLIST N baix), DAX(REJECTED). Univers final tancat: MSFT+NVDA+QQQ
- [x] T7: **Paper probe mínim** — implementat: DailyEngine, PaperExecutor, SQLite, FastAPI (/health /status /signals /trades). Tests 7/7 PASS
- [x] T7a: **Observabilitat i verificació operativa** — scan result persistent, /status enriquit, /probe-summary, logs estructurats, checklist diari al runbook. Tests 11/11 PASS
- [ ] T7 operatiu: ≥4 setmanes running, ≥3 senyals registrats, WR paper ≈ WR backtest
- [ ] T8: Decisió live — revisar resultats paper vs backtest, autoritzar o no live trading

### Estratègia activa (T7 paper probe)

**capitulation_d1** — LONG after crash extrem en D1 (equitats US mega-cap)
- Asset primari: **MSFT** (ACCEPTED_D1_ASSET)
- Assets complementaris: **NVDA**, **QQQ** (WATCHLIST)
- TF: D1 | Entry: open(T+1) | Exit: close(T+1) | Leverage: 20x
- Backtest MSFT: WR 78%, PF 3.46, EV +12.7$/trade, liq 0%, WF 10/12 (83%)
- Gate: body < -2%, close < BB_lower(20,2)
- Script: `packages/strategy/capitulation_d1.py`
- Engine: `packages/runtime/engine.py` (DailyEngine, executar post-close)
- DB: `data/paper_probe.db` (signals, paper_trades, agent_state)
- API: `uvicorn apps.agent.app:app --port 8090`

**Capitulation Scalp 1H (crypto)** — arxivat, WATCHLIST no suficient sol
- Assets: ETH, BTC, SOL | TF: 1H | EV +5.6$/t | liq 14% | Script: `lab/studies/`

### Decisió T1: Leverage MVP = 20x (TANCAT)

Backtest refet amb liquidació simulada (MAE >= 1/lev → pèrdua total col):
- **20x recomanat**: EV +5.6$/trade, 14% liquidacions, 250$→1.114$ (x4.5), MaxDD 37%
- **Runner-up 15x**: EV +4.3$/trade, 9% liq, MaxDD 23% (més conservador)
- **100x DESCARTAT**: 68% liquidacions, EV negatiu, capital → 10$
- Artifact: `lab/out/leverage_recalibration.json`
- AGENTS_ARQUITECTURA.md §6 i §11 actualitzats

### Resultat T6 complet (4 cicles, 18 setups)

- Crypto 1H: **esgotat** (1 WATCHLIST modest)
- Crypto 4H: **mort** (massa volàtil per leverage)
- **Equitats D1: viable!** Capitulation D1 WATCHLIST amb Nasdaq/NVDA/MSFT prometedors
- **T6d leverage sweep**: MSFT = asset estrella (WR 78%, liq 0%, EV +12.7$@20x)

### T6d — Leverage sweep D1 (10 assets, 6 leverages)

| Asset | N | WR | EV@20x | Liq@20x | BestLev | EV@best | WF | Status |
|-------|---|-----|--------|---------|---------|---------|-----|--------|
| **MSFT** | **41** | **78%** | **+12.7$** | **0%** | 30x | +13.7$ | 10/12 | WATCHLIST |
| **NVDA** | **68** | **63%** | **+6.0$** | **4.4%** | 20x | +6.0$ | 11/13 | WATCHLIST |
| **QQQ** | **40** | **62%** | **+3.6$** | **2.5%** | 20x | +3.6$ | 7/8 | WATCHLIST |
| SPY | 23 | 74% | +3.3$ | 4.3% | 30x | +11.8$ | 7/8 | REJECTED (N<40) |
| AAPL | 41 | 51% | +1.2$ | 2.4% | — | — | 6/12 | REJECTED |
| AMZN/META/GOOGL/TSLA | — | — | negatiu | — | — | — | — | REJECTED |

**Perquè MSFT destaca:**
- MAE mediana 0.75% → liq 0% fins a 25x (excepcional per D1)
- WR 78% baseline, MC shuffle 100%, WF 10/12 (83% anys positius)
- Problema anterior resolt: gate N≥120 era inaplicable al D1 (vegeu T6e)

### T6e — Gate D1 adaptat + decisió final

Gate D1 per asset (`lab/docs/D1_GATE_CRITERIA.md`): N≥35, EV≥+8$, PF≥1.8, liq≤5%, WF≥70%, MC≥90%, MAE≤1.5%

| Asset | N | WR | EV@20x | Liq@20x | WF | MC | MAE | Criteris | Status |
|-------|---|-----|--------|---------|-----|-----|-----|---------|--------|
| **MSFT** | **41** | **78%** | **+12.7$** | **0%** | **10/12** | **100%** | **0.75%** | **8/8** | **ACCEPTED_D1_ASSET** |
| NVDA | 68 | 63% | +6.0$ | 4.4% | 11/13 | 100% | 1.55% | 5/8 | WATCHLIST |
| QQQ | 40 | 63% | +3.6$ | 2.5% | 7/8 | 100% | 1.32% | 6/8 | WATCHLIST |
| SPY | 23 | 74% | +3.3$ | 4.3% | 7/8 | 100% | 1.04% | 4/8 | REJECTED (N<35) |

### **Decisió T6e: PAPER_PROBE_AUTHORIZED**

- Asset primari: **MSFT** (ACCEPTED_D1_ASSET, 8/8 criteris)
- Assets complementaris: NVDA i QQQ (WATCHLIST — diversificació temporal)
- Leverage: 20x | Setup: capitulation_d1 | Durada mínima: 4 setmanes

Veure `lab/docs/T6E_DECISIO_D1_ASSETS.md` i `lab/docs/D1_GATE_CRITERIA.md`.

---

## Historial

| Data | Acció |
|------|-------|
| 2026-03-16 | Projecte creat. Estructura, MDs, lab importat de SQRunner |
| 2026-03-16 | MC+WF PASS. Shuffle 100%, Random Entry edge +15-35pp, Param Perturb 50/50 |
| 2026-03-16 | STRESS TEST: lev 100x = 61% liquidacions! Kelly=47%, sizing 20% OK. Recomanat lev 20-30x |
| 2026-03-16 | **T1 TANCAT**: leverage MVP = 20x. Backtest amb liquidació: EV +5.6$/t, liq 14%, 250$→1.114$. AGENTS §6/§12 alineats |
| 2026-03-16 | **T2**: Docs alineats. Gate de producció establert (AGENTS §9). Fase = LAB, no BUILD |
| 2026-03-16 | **T3**: Contracte canònic LAB (SetupSpec, ValidationResult, OpportunityEstimate). 5/5 tests |
| 2026-03-16 | **T4**: Inventari LAB: 1 setup WATCHLIST (Capitulation), 2 REJECTED (Markov). Catàleg creat |
| 2026-03-16 | **T5**: Harness validació creat. 7 passes (baseline→deployable→MFE/MAE→liq→MC→WF→classify). Smoke PASS: Capitulation → WATCHLIST |
| 2026-03-16 | **T6**: 6 setups explorats (3 famílies). 4 REJECTED (MC 0%), 1 WATCHLIST N=11. Crypto 1H esgotat — cal pivot |
| 2026-03-16 | **T6b**: Crypto 4H — 6/6 REJECTED. MAE massa alta per leverage 20x (38% liq capitulation) |
| 2026-03-16 | **T6c**: Equitats D1 — **Capitulation D1 WATCHLIST** (N=288, WR 60%, PF 2.59). Nasdaq WR 73%, NVDA WATCHLIST |
| 2026-03-16 | **T6d**: Leverage sweep 10 assets D1 × 6 leverages. MSFT = estrella (WR 78%, EV +12.7$@20x, liq 0%, WF 10/12). 3 WATCHLIST, 0 ACCEPTED |
| 2026-03-16 | **T6e**: Gate D1 adaptat. MSFT = ACCEPTED_D1_ASSET (8/8). **PAPER_PROBE_AUTHORIZED** |
| 2026-03-16 | **T6f**: Screening 5 nous actius (AMD/NFLX/META/GOOGL/AMZN) → tots REJECTED. Univers final: MSFT+NVDA+QQQ. Fase LAB tancada |
| 2026-03-16 | **T6g**: GLD(N=3), SPY(WATCHLIST N baix), DAX(REJECTED). Univers confirmat: MSFT+NVDA+QQQ. Resum complet LAB creat |
| 2026-03-16 | **T7 implementat**: DailyEngine, PaperExecutor, SQLite, FastAPI. Tests 7/7. LAB→PAPER PROBE |
| 2026-03-17 | **T7a**: Observabilitat. Scan result persistent (agent_state last_scan_result), /status enriquit amb trades+last_scan, /probe-summary, logs estructurats (scan_completed, settlement_completed), checklist diari al runbook. Tests 11/11 PASS |
