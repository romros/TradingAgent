# ESTAT.md — TradingAgent

Operativa diària i evidència. Actualitzar a cada canvi significatiu.

---

## Estat actual (2026-08-10)

### Continuïtat SQ / DuckDB / Ostium

Pla canònic per automatitzar campanyes SQ, validar preus i operacions amb DuckDB/BS i calcular mida, collateral i leverage segur per Ostium: [`docs/SQ_AUTOMATION_OSTIUM_PLAN.md`](SQ_AUTOMATION_OSTIUM_PLAN.md). SQCLI torna a tenir una trial activa.

### Alquímia — laboratori quantitatiu

**EURUSD D1 v4 — dades certificades, costos en maduració:** el pont nou de dues
potes evita exigir un solapament inexistent: SQ↔Dukascopy coincideix en 9.827 M1
amb OHLC 100%, i Dukascopy↔Ostium coincideix en 122 dies complets amb correlació
de retorn 0,9999996, direcció 100% i close p95 0 bps. Decisió
`PASS_D1_SOURCE_MAPPING`, sense consultar rendiment. No autoritza SQCLI: falta el
gate de 30 quotes, 3 dies i 6 hores UTC de costos EURUSD per a 200 USDC. La font
Dukascopy també passa cobertura 2003-05-05–2026-02-27: 5.884/5.955 sessions,
98,81% global i 91,92% al pitjor any. L'export D1 completa del recurs SQ antic
queda rebutjada: només 23,29% OHLC exactes, màxim 209,4 bps, 1.188 fragments de
diumenge i 1.324 barres incompletes. Cal construir un símbol nou des dels
Parquet hashejats i certificar-ne el roundtrip. Detall a
[`EURUSD_D1_SOURCE_MAPPING_V4.md`](EURUSD_D1_SOURCE_MAPPING_V4.md).
El job multi-mercat ja recalcula automàticament el freezer i el preflight EURUSD
després de cada captura. Amb 2/30 mostres, 1/3 dies i 2/6 hores retorna `BLOCK`;
el preflight també bloqueja el recurs SQ antic. Només costos i recurs PASS podran
obrir `hypothesis_screen`, mai SQCLI o paper directes.

Arquitectura a [`docs/ALQUIMIA.md`](ALQUIMIA.md). Pilot `TA_SQ_PILOT`: NVDA/USD M1/tick, límit 20, manifest amb hashes i originals intactes. Eines a `lab/sq_bridge/`: preparador CFX, allowlist/gate Ostium, estat compacte i watchdog. Generació correcta i sense errors tècnics; acceptació inicial 0%. Watchdog: stop a 1.000 candidates sense acceptades, RAM host <1 GB o disc <2 GB.

**XAUUSD H4:** Retest SQCLI reparat fent servir un contracte Retest H4 nadiu.
Shortlist estructural 8/60 validada sobre 2015-02-07–2019-07-16: **0/8 PASS**.
Millors PF: `0.106720` 1,06; `0.34159` 1,05; `0.7893` 1,04 (gate 1,15).
Holdout 2023-12-24–2026-03-13 intacte. Aquesta fornada no avança.

**XAUUSD H4 stop-breakout R2:** nova hipòtesi dirigida. 40 descoberts de 63
intents; 10 passen validació, 4 passen OOS i `0.26`, `0.33`, `0.37` passen costos
2× i Monte Carlo de paràmetres (3.003 membres executats). `0.37` té 5/5 anys OOS
positius i 0 liquidacions proxy a 20x, però falla economia de 200 USDC: risc 1–2%
no arriba a EV mínim i risc 3% falla costos conservadors/estrès. Família rebutjada
per al perfil petit; holdout intacte i sense traducció/paritat.

**XAUUSD H4 compressió ATR R3:** 5/40 passen validació, 2/5 OOS i 1/2 costos
2×. El finalista `0.74` falla règims (2/5 anys positius) i economia 200 USDC
(+0,29 estrès en 130 trades). Branca descartada sense MC ni holdout.

**Alquímia v3 sweep/reclaim v4–v5:** v4 va executar un Builder nadiu nou
(~4.000 generades, 20 acceptades), però 0/20 reproduïen l'AST semàntic exacte;
rebuig terminal. V5 va fixar l'entrada sweep/reclaim i va reparar el Retester
SQCLI (`retestSelected=false` i selecció antiga buidada). El smoke real acaba en
6,01 s i produeix 1.180 trades, però perd −1.037,71. Un preflight train-only amb
18.448 H4 Dukascopy i 1.350 combinacions dóna 0 PASS en estrès i 0 membres de
regió estable. El millor long passa de PF 1,149 base a 0,878 estrès; short i
combinada perden en base. **V5 rebutjada** sense obrir validation/OOS/holdout ni
executar 5.000 optimitzacions SQ. Cadena SHA-256 terminal a
`lab/sq_bridge/evidence/xau_h4_sweep_reclaim_v5_chain.json`.

**Alquímia XAU H1 v6–v7:** v6 va preregistrar desplaçament continuació/reversió
per costat, sis blocs UTC, dies, ATR i durada: 5.184 punts train, 0 PASS d'estrès
i 0 regions estables. L'auditoria de barres va descobrir una regla tardana long
amb edge train després d'exigir ≥50 M1 observades; es va congelar com v7 amb
biaix de selecció declarat. Train: 55 trades, PF estrès 1,84 i 7/10 anys positius.
Validació independent 2015–2019: 20 trades, PF base 2,27 però PF estrès 0,85,
−0,43% i 2/5 anys positius. **V6 i v7 rebutjades**; OOS/holdout intactes.

**MSFT D1 gap/shock v8:** SQCLI exporta 6.936 D1 natives (1999–2026), però el
gate offline contra 93 sessions Ostium completes bloqueja la família abans de
Builder. Close és coherent (mediana 5,29 bps, p95 24,34; correlació 0,9979),
però open falla (mediana 29,36 bps, p95 116,30) i high/low tenen p95 229,52 i
178,78 bps. Una regla de gaps/stops no seria paritat executable. Cadena terminal
`BLOCK` sense discovery, validation, OOS ni holdout.

**XAU D1 inside-day v9:** gate previ accepta Dukascopy com a proxy de recerca
XAU (corr retorn 0,971; direcció filtrada 96,69%) però no per live; BTC queda
bloquejat per manca d'històric Ostium nadiu. La família D1 prova 1.944 punts
preregistrats amb costos i funding: 0 PASS i 0 regions estables. Després de
fixar una sola posició oberta, els millors PF estrès són 1,003 long i 0,996
short. **V9 rebutjada en discovery**, sense SQCLI ni obrir validació.

**XAU D1 trend-pullback v10:** 25/324 punts passen train i formen una regió
connectada, tota long. El medoid topològic EMA200/RSI3≤10/stop1,5ATR/2 dies té
PF estrès 1,51 en train, però falla la validació 2015–2019: 11 trades, PF 0,097,
−6,46% i 0/3 anys positius. **V10 rebutjada temporalment**; OOS/holdout intactes.

**BTCUSD recorder:** activat a BrokerageService per hot-reload sense reinici ni
trading. Feed perp verificat, ticks/candles persistents i zero errors. Gate de
maduració: 60 dies i ≥90% cobertura; estat inicial `WARMING`, no abans de
2026-10-02. El gate d'univers exigeix després paritat explícita BTCUSDT/BTCUSD.
El `.dat` BTCUSDT actual falla export SQ 143 (`Unknown logic type of value 3`),
queda congelat i bloquejat, sense sobreescriure'l.

**BTC v11–v12:** font oficial 2018–2026 (4.377.479 M1) verificada. V11 prova
1.032 variants; dues regions long estables de train fallen 2022–2023 amb PF
estrès 0,70/0,65. V12 consumeix aquest tram com a desenvolupament i prova 216
breakouts amb règim D1; el representant short PF 1,56 cau a 3/3 pèrdues en la
nova validació 2023-07–2024-06. `REJECT_BTC_PROXY_FAMILIES_NO_SQCLI`; OOS i
holdout intactes, cap paper/live.

**BTC v13–v14:** 288 breakouts de sessió produeixen 0 PASS. La inversió fade
produeix 1 punt aïllat però 0 regions estables. `REJECT_BTC_SESSION_FAMILIES`;
validació/OOS/holdout intactes i sense SQCLI. ETHUSD i SOLUSD s'han afegit al
recorder natiu: primers M1 verificats, estat `WARMING` fins almenys 2026-10-02.

**Crypto multi-actiu v15–v17:** fonts Binance oficials i hasheades disponibles
per BTC (4.377.479 M1), ETH (3.938.630) i SOL (3.064.335). V15 té 0/192 PASS;
V16 2/96 però cap regió estable; V17 forma una regió estable (14/225) però el
medoid passa de PF estrès 1,19 i +5,59% en desenvolupament a PF 0,62 i -2,33%
en validació 2024H2. `REJECT_CRYPTO_MOMENTUM_NO_OOS_NO_SQCLI`; OOS/holdout
intactes. ETH i SOL ja són a SQ en símbols nous: roundtrip juny 2026 amb
43.200 timestamps i OHLC exactes. Volum fraccional truncat, de manera que són
`PASS_SIGNAL_RESEARCH` exclusivament; paper/live i regles de volum bloquejats.

**Crypto compressió intradia v18:** 17/2.304 punts passen desenvolupament i
dues regions petites seleccionen BTC short i ETH long, 00 UTC laborables. Els
medoids semblen forts en 2021–2024 (PF estrès 1,47/1,70; +0,37/+0,56 USDC per
trade; 0 liquidacions), però fallen la validació 2025H1: BTC 6 trades, PF 0,73,
-0,41 USDC/trade; ETH 4/4 pèrdues, -1,32 USDC/trade. Branca terminal
`REJECT_CRYPTO_INTRADAY_COMPRESSION_NO_SQCLI`; holdout intacte, sense Builder,
paper ni live.

**Ledger temporal + crypto capitulació/reclaim v19:** el gate global impedeix
reutilitzar dades ja vistes com a OOS independent; 2025H2–2026H1 queda reservat
per una sola cohort. V19 prova 11.664 punts i troba una regió BTC long de 9
membres. Discovery: 45 trades, PF estrès 1,60 i +0,41 USDC/trade. Walk-forward
intern agregat: 27 trades, PF 2,05 i +12,43%, però falla mostra (27<30), mínim
per fold (2<3) i consistència (3/5 folds positius, mínim 4/5). Rebuig terminal
`REJECT_CRYPTO_CAPITULATION_RECLAIM_INTERNAL_WF`, sense SQCLI ni holdout.

### Fase: PAPER PROBE — T7 en curs (≥4 setmanes, inici 2026-03-16)

**Setup actiu**: `capitulation_d1` — MSFT (primari), NVDA, NDXUSD (complementari, paper: QQQ proxy)
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
- [x] T7b: **Validació paper vs backtest** — polish T7a (probe_ok determinista, winrate robust), mètriques paper, baseline MSFT (WR 78%, EV +12.7$), classificació aligned/warning/diverged, endpoint /validation. Tests 19/19 PASS
- [x] T7c: **Traçabilitat temporal + validació data source** — taules scan_runs, validation_runs; equity curve i drawdown; validate_candles (OHLC, gaps, count); endpoints /probe-history, /data-quality. Tests 26/26 PASS
- [x] T8a: **Auditoria BrokerageService** — bs_probe: fetch BS, agregar 1m→D1, validar, comparar vs yfinance; endpoint /bs-audit; classificació aligned/warning/diverged. Tests 31/31 PASS
- [x] T8b: **Validació proxy QQQ vs NASDAQUSD** — correlació returns, avg_delta_pct; endpoint /proxy-validation; classificació aligned|warning|diverged|insufficient_data. Tests 42/42 PASS
- [x] T8c: **Decision Gate Live Readiness** — compute_live_readiness; endpoint /live-readiness; status LIVE_READY|LIVE_SHADOW_READY|LIVE_NOT_READY; reasons. Tests 53/53 PASS
- [x] T7d: **Snapshot diari automàtic** — build_daily_snapshot; fitxer Markdown a data/probe_snapshots/YYYY-MM-DD.md; POST /snapshot; trigger al final del cicle diari; validation, live-readiness, data-quality, trades, proxy-validation, bs_audit. Tests 57/57 PASS
- [x] T8d: **Arrencada real + scheduler + quick-status** — docker compose up -d; scheduler diari (SCHEDULER_HOUR_UTC=21); /quick-status; healthcheck; restart unless-stopped. Tests 59/59 PASS
- [x] T8d-v: **Validació operativa + fix assets** — PROBE_ASSETS: QQQ→NDXUSD (canònic executable); YF_SYMBOL_PROXY NDXUSD→QQQ; agent_started amb assets; test_probe_assets_config_canonical. Tests 57/57 PASS. Smoke: ver docs/T8D_V_SMOKE.md
- [x] T8e: **Model de proves Docker-only** — run.sh (component, integration, smoke, soak); run_all.sh; test.sh delegat; scripts Python purs (NO pytest); scripts/README.md. Smoke i soak reals dins Docker.
- [x] T8e-v: **Validació final + artifacts públics** — run_all.sh escriu a docs/validation/; LATEST.md amb raw URLs; smoke/soak artifacts versionats.
- [x] T7e: **Reconciliació de costos paper** — PnL brut reconstruït des de preus/nominal; escenaris 6/10/18 bps; API, validació i equity canònics; trades antics immutables i backup verificat. 50 tests PASS.
- [x] T9: **Campanya petit inversor — NO_CANDIDATE** — 6 famílies individuals + 3 carteres, split temporal immutable, costos 2x i leverage condicionat al risc. 0 candidates acceptades; `short_term_reversal` rebutjada per mostra (14 total, 1 test). Veure `lab/docs/SMALL_INVESTOR_CAMPAIGN_FINAL.md`.
- [x] T10: **Campanya intradia FX — NO_CANDIDATE** — 6 famílies sobre EURUSD/XAUUSD 4H, 2004–2026, costos 2x i límits BS de 10x/50 USD. 0 configuracions viables en desenvolupament; la millor quasi-candidata falla validació (PF 0,48). Veure `lab/docs/INTRADAY_FX_CAMPAIGN_FINAL.md`.
- [ ] T7 operatiu: ≥4 setmanes running, ≥3 senyals registrats, WR paper ≈ WR backtest
- [ ] T8: Decisió live — revisar resultats paper vs backtest, autoritzar o no live trading

### Estratègia activa (T7 paper probe)

**capitulation_d1** — LONG after crash extrem en D1 (equitats US mega-cap)
- Asset primari: **MSFT** (ACCEPTED_D1_ASSET)
- Assets complementaris: **NVDA**, **NDXUSD** (WATCHLIST; paper: QQQ proxy via yfinance)
- TF: D1 | Entry: open(T+1) | Exit: close(T+1) | Leverage: 20x
- Backtest MSFT: WR 78%, PF 3.46, EV +12.7$/trade, liq 0%, WF 10/12 (83%)
- Paper actual: 6 trades, WR 50%, brut +20.89$, base +17.56$, conservador +15.33$, estrès +10.88$; mostra encara insuficient.
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
- Assets complementaris: NVDA i NDXUSD (WATCHLIST; runtime: NDXUSD, backtest: QQQ)
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
| 2026-03-17 | **T7b**: Validació paper vs backtest. Polish T7a: probe_ok (<48h, sense errors), winrate robust (<3 trades→confidence=low). Baseline MSFT 78%/12.7$. Mètriques paper, classificació aligned/warning/diverged, /validation. Tests 19/19 PASS |
| 2026-03-17 | **T7c**: Traçabilitat temporal + data source. scan_runs, validation_runs; equity curve, drawdown; validate_candles (OHLC, gaps≥200); /probe-history, /data-quality. Tests 26/26 PASS |
| 2026-03-17 | **T8a**: Auditoria BrokerageService. packages/market/bs_probe.py: fetch BS 1m, agregar D1, validar, comparar vs yfinance; /bs-audit; classificació aligned/warning/diverged. Tests 31/31 PASS |
| 2026-03-17 | **T8b**: Validació proxy QQQ vs NASDAQUSD/NDXUSD. run_proxy_validation: returns, correlació Pearson, avg_delta_pct; /proxy-validation; aligned (corr≥0.95, δ<1%) | warning (corr≥0.90, δ<3%) | diverged | insufficient_data (samples<30). Tests 42/42 PASS |
| 2026-03-17 | **T8c**: Decision Gate Live Readiness. compute_live_readiness; /live-readiness; agregació validation+proxy+data_quality+bs_audit; status LIVE_READY|LIVE_SHADOW_READY|LIVE_NOT_READY; reasons. Tests 53/53 PASS |
| 2026-03-17 | **T7d**: Snapshot diari automàtic. packages/runtime/daily_snapshot.py; build_daily_snapshot; data/probe_snapshots/YYYY-MM-DD.md; POST /snapshot; trigger al final engine.run(); reutilitza funcions canòniques; degradació amb secció error si falla. Tests 57/57 PASS |
| 2026-03-17 | **T8d**: Arrencada real. Dockerfile + compose.yml; docker compose up -d; scheduler APScheduler (21:00 UTC); /quick-status; healthcheck; SCHEDULER_ENABLED, SCHEDULER_HOUR_UTC; scan_runner; Tests 59/59 PASS |
| 2026-03-17 | **T8d-v**: Validació operativa + fix assets. PROBE_ASSETS=MSFT,NVDA,NDXUSD; YF_SYMBOL_PROXY (NDXUSD→QQQ); agent_started assets; test_probe_assets_config_canonical. Tests 57/57 PASS |
| 2026-03-17 | **T8e**: Model proves Docker-only. run.sh component|integration|smoke|soak; run_all.sh; test.sh→run.sh; scripts Python purs (NO pytest); scripts/README. Smoke+soak reals dins Docker |
| 2026-03-17 | **T8e-v**: Validació final. Artifacts a docs/validation/; LATEST.md raw https://raw.githubusercontent.com/romros/TradingAgent/main/docs/validation/LATEST.md |
| 2026-08-01 | **T7e costos paper**: eliminat el biaix de 5.38$ fixos del reporting; 6 trades preservats, estat reconciliat a capital 267.56$ i PnL base +17.56$; API amb brut/recorded/base/conservative/stress. |
| 2026-08-01 | **T9 recerca petit inversor**: 6 famílies individuals + 3 carteres; execució next-open, costos/finançament, liquidació, OOS i leverage sense contaminar test. Resultat **NO_CANDIDATE** |
| 2026-08-01 | **T10 recerca intradia FX**: EURUSD/XAUUSD M1→4H, 6 famílies, split dev/validació/test, gas+spread+finançament, leverage màxim BS 10x i auditoria bootstrap. Resultat **NO_CANDIDATE** |
| 2026-08-01 | **Pla SQ → Ostium documentat**: SQCLI, databank, paritat DuckDB, traducció controlada, matching d'execució i sizing/leverage condicionat al risc. |
| 2026-08-02 | **XAUUSD H4 shortlist validada**: incidència Retest resolta amb plantilla H4 nativa; 8 famílies retestades, 0 PASS (PF màxim 1,06 vs gate 1,15); holdout intacte. |
| 2026-08-02 | **XAU H4 stop-breakout R2 prometedor**: 3 candidats passen validació, OOS, costos 2× i MC de paràmetres 1.000×; encara no autoritzats per holdout/paper. |
| 2026-08-02 | **XAU H4 stop-breakout R2 tancat per compte petit**: `0.37` estable i segura a 20x, però EV insuficient amb 200 USDC; a risc 3% només passa base. Holdout preservat. |
| 2026-08-02 | **XAU H4 compressió ATR R3 descartada**: millora durada però falla amplitud temporal i EV de 200 USDC; no s'executa MC ni holdout. |
| 2026-08-02 | **MSFT D1 close v1**: 80 SQ → 48 Pareto → 8 validació/OOS → 3 finalistes congelats. `calendar long 0.14` és el millor (holdout 29 trades, PF estrès 1,66), però continua `LIVE_NOT_READY` per paritat OHLC/Ostium, gaps/liquidació i paper pendents. |
| 2026-08-02 | **MSFT calendar 0.14 falsificada**: paràmetres estables (27/27), però no supera 500 calendaris mensuals aleatoris en validació/OOS/holdout; 21× també mostra un gap històric més gran que el proxy de liquidació. `REJECT_CALENDAR_TIMING_EDGE`; no passa a paper. |
| 2026-08-02 | **Revisió estratègies famoses**: TSMOM EURUSD+XAU és positiu brut a 126d però el rollover Ostium elimina l'edge; ORB XAU COMEX perd abans d'estrès (millor OOS PF 0,81). Holdouts preservats. Només `capitulation_d1` continua en paper. |
| 2026-08-02 | **Capitulació confirmada v1**: 36 variants close-only per actiu sobre MSFT/NVDA/QQQ. MSFT falla validació (PF base 0,82; p aleatori 0,83), NVDA col·lapsa fora de train (PF 0,35/0,75) i QQQ és negatiu. Decisió `REJECT_HOLDOUT_REMAINS_SEALED`; 2024–2026 no consultat. |
| 2026-08-02 | **Anatomia capitulation_d1**: l'edge congelat T+1 intradia supera timing aleatori en MSFT/NVDA/QQQ, però 20x no és segur amb història ampliada (liq proxy 2,70%/7,64%/2,41%). Nous caps per operacions paper: MSFT 10x, NVDA i NDXUSD 5x; risc 1%, no live. |
| 2026-08-02 | **Paper risk sizing v2**: noves operacions amb stop i nocional `capital×1%/stop`, caps MSFT 10x/NVDA 5x i costos 8/15/30 bps. EV estrès a 200 USDC: MSFT +0,288, NVDA +0,169, QQQ +0,069; NDXUSD surt del probe per defecte i queda watchlist. Històric intacte. |
| 2026-08-02 | **Risk glidepath**: risc 1,5% sota 400 USDC i reducció escalonada fins 0,5% sobre 5.000. MSFT+NVDA conservador: 200→303,23 en 23,05 anys, DD 4,67%, sense arribar a 400; confirma que falten edges independents. |
| 2026-08-02 | **EURUSD intradia v2**: 549.497 M15 Dukascopy, DST Londres/NY, 10 pilots. Breakout asiàtic PF base val/OOS 0,31/0,22; expansió continuació 0,11/0,06; reversió 0,07/0,06. `REJECT_NO_SQCLI`, holdout segellat. |
| 2026-08-03 | **Alquímia v3 + sweep/reclaim v4–v5**: contracte natiu amb rebuts SHA-256 i holdout segellat. V4 genera 20 SQX però 0 passen semàntica; v5 executa seed fix real i 1.350 punts Dukascopy, amb 0 PASS d'estrès. Cadena terminal verificada; 171 tests + 4 subtests PASS. |
| 2026-08-03 | **XAU H1 displacement v6–v7**: 5.184 punts per mecanisme/costat/hora/dia. V6 sense regió; v7 tardana congelada passa train però falla validació en estrès (PF 0,85). OOS/holdout no consultats. |
| 2026-08-03 | **MSFT D1 gap/shock v8**: export SQ nadiu 6.936 D1; close passa paritat recent però open/high/low fallen. Família bloquejada a market preflight, abans de Builder. |
| 2026-08-03 | **Gate XAU/BTC + XAU D1 v9**: XAU apte només per recerca, BTC bloquejat per paritat absent. Inside-day: 1.944 punts train, 0 PASS/regions; rebuig terminal sense SQCLI ni holdout. |
| 2026-08-03 | **XAU D1 trend-pullback v10**: 25/324 PASS train en una regió; medoid triat sense PF. Validació: 11 trades, PF estrès 0,097 i −6,46%. Rebuig terminal; OOS/holdout segellats. |
| 2026-08-03 | **BTCUSD recorder natiu**: afegit a BS, 11/11 símbols preservats, feed perp i persistència verificats. Gate 60 dies en `WARMING`; font SQ BTCUSDT existent no exportable i congelada. |
| 2026-08-03 | **BTC SQ reconstruït, només recerca**: 43.200 M1 oficials Binance amb checksum importades a `BTCUSDT_BINANCE_M1`; round-trip SQ conserva files/timestamps i limita l'error OHLC a 0,05 USD. Volum arrodonit: prohibit usar-lo; paper/live bloquejats. |
| 2026-08-03 | **BTC v11–v12 falsificades**: 4.377.479 M1 oficials; v11 1.032 punts → 2 regions estables → 0/2 validació. V12 216 punts → 1 regió short → 3/3 pèrdues validació. No SQCLI, OOS/holdout segellats. |
| 2026-08-03 | **BTC v13–v14 + ETH/SOL recorder**: breakout sessions 0/288; fade 1 punt però 0 regions. No validació/SQCLI. Recorders ETHUSD/SOLUSD actius, primers M1, 13 símbols totals. |
| 2026-08-03 | **Crypto universal reclaim v20**: 3.888 regles comunes BTC/ETH/SOL, 3 PASS aïllats però 0 regions amb ≥2 veïns. Millor PF estrès 1,41 i +0,60 USDC/trade, però SOL quasi pla. `REJECT_CRYPTO_UNIVERSAL_RECLAIM_NO_STABLE_REGION`; sense WF/SQCLI/holdout. |
| 2026-08-03 | **Crypto Donchian-ATR H4 v21**: 5.184 punts → regió estable de 12; medoid discovery PF 1,51. Walk-forward 147 trades, PF 0,91, −4,73%, DD 17,96%, 1/5 folds positius. `REJECT_CRYPTO_DONCHIAN_ATR_INTERNAL_WF`; sense SQCLI/holdout/paper. |
| 2026-08-03 | **Market preflight v22**: EURUSD/XAUUSD bloquejats perquè la paritat més recent és PARTIAL; MSFT/NVDA/NDXUSD sense històric certificat. 0 mercats elegibles, 0 performance consultada; campanya v22 no iniciada. |
| 2026-08-03 | **Paritat MSFT neta v23**: després de reparar el recorder/rollover de BS, 80 sessions completes SQ↔Ostium donen close mediana 4,74 bps, p95 19,41 bps, correlació 0,9984 i direcció 100%. Open/high/low continuen fora de tolerància: només autoritza recerca close-only, no gaps/stops intradia ni paper/live. La calendar 0.14 continua rebutjada per timing no superior a l'atzar i risc de gap a 21×. |
| 2026-08-04 | **MSFT close-drift v24**: 54 variants preregistrades amb senyal D-1, entrada/sortida al close i 36 bps. Cinc passen el gate formal, però l'auditoria ±20% deixa un únic clúster robust: SMA100 + pullback ROC5 ≤−2% + hold 5 (42/81 veïns). És evidència històrica no independent i només candidat a forward paper. 8× registra una liquidació proxy per excursió adversa close del 19,07%; cap provisional 4×. |
| 2026-08-04 | **Feed forward MSFT v24**: BS exposa `ostium_clean` (només Parquet quarantinat); TA combina aquest històric amb la sessió actual, validada fail-closed. Smoke real: 80 sessions completes de 102 requerides, estat `WARMING_UP`, cap senyal ni operació. El probe actual `capitulation_d1` no s'ha modificat. Context Docker reduït de >2,28 GB a ~1,24 MB excloent Academia i venvs. |
| 2026-08-04 | **Motor paper MSFT v24**: ledger SQLite separat, 200 USDC, 4x, sizing per risc 1%/adverse move 19,07% (nocional inicial 10,49 USDC), 36 bps roundtrip i sortida a cinc sessions. Proves: warm-up, idempotència, compounding i liquidació. Smoke BS real persisteix `WARMING_UP`, capital 200, 0 trades; encara no connectat al scheduler. |
| 2026-08-04 | **Scheduler multi-probe desplegat**: `capitulation_d1` continua a 21:00Z amb 6 trades preservats; `msft_close_drift_v24` s'executa a 21:10Z contra BS `ostium_clean`, DB independent i gate automàtic 102 sessions. Salut OK; scan manual: 80/102, `WARMING_UP`, capital 200, 0 trades. Backup previ a `data/backups/paper_probe_before_multistrategy_20260804.db`. |
| 2026-08-04 | **MSFT v24 bloquejada abans d'operar**: la documentació oficial d'Ostium confirma que les accions operen 09:30–16:00 ET i que les posicions day-trade es tanquen a les 15:45 ET. El fill al close de 16:00 del backtest no és executable. Scheduler desactivat i runner `BLOCKED_EXECUTION_WINDOW`; 0 trades afectats. Els 36 bps també ometien l'oracle fix de 0,10 USD, material amb nocional de 10,49 USD. Cal redisseny pre-close o next-open i revalidació completa. |
| 2026-08-04 | **Ràfega Dukascopy tallada**: l'snapshot de les 21:00 consultava variants MSFT/NVDA/NDX sense `source`; BS feia fallback Dukascopy sobre símbols incompatibles i provocava HTTP 429 just abans dels pilots. L'auditoria ara força `source=ostium_clean` i `NDXUSD` surt del compose operatiu. |
| 2026-08-05 | **GBPUSD M1→H1/H4 pilot**: downloader reprenable completa juliol (32.773 M1) i dos dies solapats. Agregador OHLCV canònic reconstrueix M5/M15/H1/H4 i D1 NY-close/DST. En 43 H1 completes: corr 0,9985, direcció 100%, OHLC p95 <1 bp. `PASS_H1_MAPPING_PILOT_EXTEND_SAMPLE`; M1 bloquejat i D1/H4 encara amb mostra curta. |
| 2026-08-06 | **Pilot SQ ATR H4 v1 auditat**: EURUSD 251 intents→40 i XAUUSD 259→40, 0 errors i 80/80 artifacts conformes (`EnterAtStop+Highest/Lowest+ATR`). Tots rebutjats: el CFX heretava `FixedSize=1` i no aplicava el DD≤15% declarat; 0/80 passen el gate real. US500 no s'executa per recurs no resolt. Controlador GUI/WS determinista implementat i v2 `RISK1` preregistrada amb sizing 1% i DD≤15% dins SQ. |
| 2026-08-06 | **ATR H4 RISK1 v2**: amb sizing 1% i `DrawdownPct≤15` real, EURUSD fa 529 intents→40 (13 famílies) i XAU 1.000→4 (4 famílies), 0 errors i 44/44 contractes estructurals PASS. Només IS 2017–2021: no són candidats productius. Decisió congelada: retestar els 44 a validació 2022–2025-07 sense consultar holdout. |
| 2026-08-03 | **Auditoria recorder equity**: trobats 95–120 dies natius, però rollover/API històrica desconnectats i contaminació M1 al final de sessió (MSFT/NVDA fins 16%); probable preu nou amb timestamp vell. Gate natiu bloqueja performance fins fix+rebuild BS. |
| 2026-08-06 | **Pilot SQ ATR risk1 tancat abans del holdout**: 40 EURUSD i 4 XAUUSD congelades; validació independent deixa 2/40 EURUSD i 0/4 XAUUSD. Els dos supervivents EURUSD fallen l'economia Ostium d'un compte de 200 USDC (base: −12,40/PF 0,34 i −5,25/PF 0,66), incloent fee, oracle, execució i rollover 4/8/12% anual. Família rebutjada; holdout 2025-08–2026-07 intacte. |
| 2026-08-06 | **EURUSD London ORB v25 descartat abans de SQCLI**: 72 variants preregistrades, M15 Dukascopy, entrada confirmada i sortida el mateix dia. Amb 200 USDC, risc 1%, oracle 0,10 i 4,5/7/10 bps, 0 variants passen els gates de train 2007–2014. Validació, OOS i holdout no s'utilitzen per rescatar-la; no es gasta SQCLI. |
| 2026-08-08 | **Font GBPUSD preparada, accés bloquejat**: la paritat pilot Ostium↔Dukascopy és prometedora a M15 (corr. 0,989; diferència close p95 0,82 bps), però BS només té un mes consolidat. SQCLI no pot exportar els `.dat` perquè la trial ha expirat. L'arxiu M1 BID mensual és atòmic, resumible i amb SHA-256, però el smoke 2023-01 rep HTTP 503/timeouts de Dukascopy i rebutja el mes sense escriure una partició incompleta. Cal renovar SQ o reprendre quan la font pública sigui estable. |
| 2026-08-08 | **Nova trial SQ validada i GBPUSD exportat**: 6.357.261 M1 (2007–2023), normalitzades des de New York amb DST a epoch UTC; 0 duplicats i 0 OHLC invàlids. La paritat de preu comuna és forta (M15 corr. 0,995/p95 0,98 bps; H1 corr. 0,999/p95 0,89 bps), però les particions Ostium antigues només cobreixen 83%/78% perquè eliminaven dies sencers. Mapping PASS; recerca de rendiment i paper BLOCK fins reconstruir raw amb quarantena per buckets i cobertura ≥95%. |
| 2026-08-08 | **GBPUSD M15 desbloquejat amb raw, H1/H4 no**: sobre juliol raw, cinc buckets H1 de rollover detectats només amb Ostium s'exclouen simètricament. M15 passa amb 2.071 barres completes, cobertura 95,66%, correlació 0,9921 i close p95 0,75 bps; H1 queda al 90,91%. El primer screen congelat de 10 variants (rang asiàtic i expansió continuació/reversió) falla clarament amb costos 8/15/30 bps i no arriba a SQCLI. |
| 2026-08-08 | **Branca breakout GBPUSD M15 descartada**: Donchian v2 (12 variants) falla perquè gira en unes 4 h; la nova v3 de canals 2/4/8 dies i permanència mínima 1/2 dies també falla perquè els stops 3 ATR tanquen en 10–15 h. Long/short són negatius a train, validació i OOS fins i tot amb cost base. Holdout intacte; no SQCLI ni rescat post-hoc. |
| 2026-08-08 | **SPXUSD M15 desbloquejat per recerca**: `SP_M1_dukas` actualitzat oficialment i normalitzat des del rellotge broker `America/New_York+07`. En el tram comú 15/03–08/07 contra el recorder natiu Ostium: 7.176 M15 completes, cobertura 95,81%, corr. 0,9895, direcció 96,71% i close p95 8,79 bps. H1 (94,75%) i H4 bloquejats; paper/live bloquejats fins auditar horaris i economia d'execució. |
| 2026-08-08 | **Economia SPX/USD auditada per recerca**: fonts oficials confirmen 3 bps d'obertura, 0 de tancament, oracle de 0,10 USDC (retornat en tancament complet), bid/ask, rollover continu i màxim publicat de 200x. La porta de recerca M15 pot usar escenaris de cost, però paper/live segueixen bloquejats fins capturar `getPairs()` normalitzat, spread/slippage per sessió, rollover long/short i MAE/stop OOS. Model reproduïble: `lab/sq_bridge/spxusd_execution_economics.py`. |
| 2026-08-08 | **SPX M1 complet exportat i primer screen M15 descartat**: API local de SQ exporta 3.977.597 files (19/01/2012–08/07/2026), normalitzades a UTC i verificades per hash. Cap de 144 variants preregistrades de gap/opening-drive, continuació/reversió, direcció, dies i sortides supera desenvolupament a 15 bps; no s'executa SQCLI. Un primer càlcul va consultar indegudament OOS 2023–2025 abans del gate: queda declarat contaminat i descartat; 2026 continua segellat. |
| 2026-08-08 | **SPX M15 compressió→expansió v2 descartada abans d'SQ**: 0 de 1.728 punts passen el gate de desenvolupament 2012–2018 amb costos 8/15/30 bps, risc 1%, marge ≤35% i liquidació Ostium exacta. Els millors PF aparents només tenen 3–5 trades en set anys: conjunció massa rara, no edge. Validació i holdout intactes; no SQCLI. |
| 2026-08-08 | **SPX M15 pullback RSI+tendència v3 descartat abans d'SQ**: 0 de 1.944 punts passen desenvolupament. No és només falta de mostra: 790 punts tenen ≥100 trades, però el millor PF amb cost base 8 bps és 0,51 i amb estrès 30 bps és 0,08. Validació/holdout intactes; aturada de nous grids SPX fins mesurar spread live i preregistrar un mecanisme econòmic diferent. |
| 2026-08-08 | **Capturador econòmic Ostium read-only operatiu**: SDK oficial TS 0.7.0, Node per digest, lockfile i `npm audit` net. Snapshot US500/USD pair 10: fee 1 bp, leverage 100x, mínim 5 USD, overnight sense restricció, spread tancat 0,97 bps, impacte 0,48 bps i rollover long/short live. Contradiu els antics 3 bps/200x. Gate automàtic: 3 captures vàlides però 0 obertes; exigeix 30 mostres, 3 dies i 6 hores UTC. Paper segueix bloquejat. |
| 2026-08-09 | **Economia SPX oberta + collector**: primera mostra de diumenge oberta: spread 1,16 bps, impacte 0,61 bps i fee 1 bp (entrada orientativa 2,78 bps). Cron read-only cada 2 h, lock anti-solapament i artifacts ignorats a `data/ostium_economics/`; gate 1/30 mostres, 1/3 dies i 1/6 hores. |
| 2026-08-09 | **SPX turn-of-month v4 descartada abans de validació**: 20 variants long-only, SQL restringit a 2012–2018. Millor punt: 80 trades, PF base 1,43 i +23,2 bps/trade, però 4/7 anys; a 30 bps PF 1,019, +1,22 bps i 3/7 anys. 0 PASS, 2019–2022/2023–2025/2026 no carregats, sense SQCLI. |
| 2026-08-10 | **Preflight extern VIX preparat**: CSV oficials Cboe VIX/VIX9D/VIX3M amb hashes, 1.760 sessions cadascun en desenvolupament 2012–2018, zero duplicats i zero OHLC invàlids al tram. VIX té 47 anomalies oficials entre 1992–2006, declarades però fora de campanya. Gate PASS només per formular un règim de volatilitat; cap rendiment d'SPX consultat i VIX no es tracta com actiu Ostium. |
| 2026-08-10 | **SPX VIX term-normalization v5 descartada**: regla fixa VIX9D/VIX3M de >1 a ≤1, entrada següent sessió 15:45, holds 1/3/5 sense solapament. 69 senyals; 0/3 PASS. Hold 3 és el millor (58 trades, PF base 1,13, 6/7 anys), però a estrès PF 0,83 i −13,15 bps/trade. 2019–2022/2023–2025/2026 intactes, sense SQCLI ni leverage. Aturada de noves famílies timing d'SPX. |
| 2026-08-10 | **GBPUSD post-London-fix v26 descartada amb cadena estricta real**: 12 punts preregistrats, només train 2007–2013. El millor té 428 trades i una tendència sense fricció mínima (PF 1,063; +0,031 USDC/trade); amb els 8 bps base congelats cau a PF 0,21 i −0,78 USDC/trade. 0 supervivents, no SQCLI, validació/OOS/holdout intactes. Cadena v2 `market_preflight PASS → discovery REJECT` verificada i terminal. |
| 2026-08-10 | **Errata v26**: l'oracle de 0,10 USDC es reemborsa en un full close correcte i no és el falsador principal. El rebuig es manté perquè els 8 bps base ja redueixen el millor punt a PF 0,21 i EV −0,78 USDC/trade. L'artefacte immutable no es reescriu; v27 separa capital bloquejat i cost net. |
| 2026-08-10 | **USDJPY M15 desbloquejat i Gotobi v27 descartada**: SQCLI exporta 7.170.956 M1 (2007–2026), EET/EEST→UTC sense duplicats ni OHLC invàlids. Després de quarantena Ostium-only simètrica, M15 passa paritat (656 completes, cobertura 98,35%, corr 0,9961, direcció 98,45%, close p95 0,92 bps); H1/H4 bloquejats. Snapshot pair 4: fee 2 bps, 100x venue. Gotobi train-only: 0/8; millor 565 trades, +1,86 bps brut però PF base 0,62/EV −0,25 USDC. Cadena estricta terminal, no Builder/validació/OOS/holdout. |
| 2026-08-10 | **USDJPY post-Tokyo-fix v28 i línia completa descartades**: sis punts short preregistrats a 10:00→14:00/16:00 JST sobre 2015–2018 donen 1.038–1.039 trades i +0,86 a +1,81 bps bruts, però tots perden amb 5 bps base (PF màxim 0,68; millor EV −0,18 USDC/trade) i a estrès tenen zero anys positius. Validació/OOS/holdout intactes, no SQCLI. Amb v27 pre-fix i v28 post-fix negatives després de costos, es tanca tota la línia Tokyo-fix sense ajustar-la post hoc. |
| 2026-08-10 | **Collector econòmic Ostium multi-mercat instal·lat**: smoke read-only confirma USDJPY, GBPUSD, EURUSD, XAUUSD i US500, amb resum genèric de fee, spread, slippage, rollover per costat, leverage i mínim nocional. Quatre mercats nous es capturen cada 4 h; US500 manté el collector dedicat cada 2 h. Una mostra només és `OBSERVED_PROVISIONAL`: multidia i paper continuen bloquejats fins 30 captures obertes, 3 dies i 6 hores UTC. |
| 2026-08-10 | **XAU FOMC v29 descartada però és la millor quasi-candidata nova**: calendari Fed oficial 2015–2026, M15 Dukascopy↔Ostium desbloquejat després de quarantena interna simètrica (604 completes, cobertura 97,73%, corr 0,9979, close p95 1,87 bps). 16 punts train 2015–2018: continuació positiva a 8 bps; millor PF 2,35/EV +0,59 USDC i a 15 bps PF 1,56/EV +0,31. A estrès 30 bps cau a PF 0,57/EV −0,39; 0 supervivents, no SQCLI, 2019–2026 intacte. |
| 2026-08-10 | **Captura FOMC d’execució preparada**: calendari Fed oficial congelat identifica el 16/09/2026 com a pròxima decisió. Collector XAU/USD read-only minutal, fail-closed fora de 13:45–16:45 NY, amb fases pre/reacció/post, nocionals 200/400/500/600 i cost proxy per spread+fees+slippage. Gate exigeix 10/20/60 minuts oberts; no reobre v29 ni autoritza paper/live. |
| 2026-08-10 | **XAU real yield + dòlar v30b també descartada abans d'SQ**: auditoria independent concurrent de la v30 d’Academia, amb episodis persistents, Dukascopy M15 i economia Ostium de 200 USDC. El preflight macro passa 417/417 setmanes i deixa 13/27 punts; 0/13 supera train 2007–2014. El millor té 36 trades i PF base/conservador 1,61/1,22, però a estrès queda PF 1,016, EV +0,014 USDC i només 3/8 anys positius. Confirma el rebuig sota un mapping alternatiu; no rescata v30. Validació/OOS/holdout intactes; no SQCLI. |
| 2026-08-10 | **Preflight CFTC Gold v32: dades PASS, timing BLOCK**: tres ZIP oficials 2010/2018/2026 confirmen esquema de 191 camps i identitat Gold `088691/088`, amb 136 reports, zero duplicats i zero posicions invàlides. No es defineix regla perquè `report_date` no és la data pública i la CFTC no ofereix el ledger històric complet; shutdowns i incidents han retardat reports setmanes. Següent pas únic: ledger oficial de publicació/exclusions. Cap rendiment XAU, SQCLI o holdout consultat. |
| 2026-08-10 | **Ledger CFTC Gold v33 PASS**: 17 ZIP oficials congelats, 866 reports Gold entre 2010 i 2026; 835 disponibles amb retard conservador de 7 dies a les 15:30 NY i 31 exclosos pels incidents oficials 2018–19, correcció Gold 2019, ION 2023 i lapse 2025. Identitat exacta `088691/088`; cap preu ni rendiment consultat. Només queda autoritzat preregistrar una regla de posicionament finita sobre train. |
| 2026-08-10 | **CFTC Managed Money v34 descartada abans d'SQ**: 27 punts de freqüència deixen un centre estable i tres veïns per train 2010–2017, però 0/4 passa. El centre executa 217 trades: brut −13,23 USDC; base PF 0,697/EV −0,188/PnL −40,80; estrès PF 0,471/PnL −84,18 i 0/8 anys positius. Long i short perden, 0 liquidacions. No invertir ni tunejar post hoc; validació/OOS/holdout intactes. |
| 2026-08-10 | **Captura US500 per sessió automatitzada**: cron read-only cada 5 minuts, fail-closed fora de 09:30–10:30, 12:00–13:00 i 15:00–16:00 NY. Recull una sola tanda de 20 quotes per finestra i dia, desa raw ignorat i resum normalitzat. El gate no s'obrirà fins a 3 dies diferents i cobertura open/midday/close; cap signer ni ordre. |
| 2026-08-10 | **Preflight VIX v35 PASS sense rendiment**: CSV oficial Cboe congelat amb 9.246 tancaments, 1990–07/08/2026, zero duplicats/caps de setmana/tancaments invàlids. 47 OHLC antics incoherents queden quarantinats i no s'usen. Política anti-look-ahead: el close VIX només val des de la sessió US500 següent. La regla continua bloquejada fins completar costos Ostium de tres dies. |
| 2026-08-10 | **Gate US500 endurit per compte petit**: exigeix 20 quotes open/midday/close en cadascun de 3 dies complets, no totals agregats. Captura slippage SDK a nocionals 60/100/200/400/500 i resumeix per sessió el proxy round-trip `spread + fee open/close + impact long/short`; rollover queda separat. Smoke real dels cinc nocionals PASS. |
| 2026-08-10 | **Transformació de costos US500 preregistrada**: només pot congelar base=p50 i conservador=p95 després del gate de tres dies; estrès usa `max(2×p50,p95)` i només aquí perd els 0,10 USDC de l'oracle. Base/conservador respecten el reemborsament del full close. Valida nocionals 60/100/200/400/500, exigeix ≥30 minuts per finestra, exclou dies parcials de l'estimació, limita credits de rollover a zero i no autoritza paper/live. Estat actual: BLOCK fins tenir tres sessions completes. |
| 2026-08-10 | **XAU abnormal-day momentum v36 preregistrada sense rendiment**: l'evidència publicada afavoreix continuació tardana el mateix dia, però la reversió de l'endemà no supera trading aleatori i queda exclosa. Nou grid finit de 36 punts, sessió Ostium NY/DST, train 2007–2014 i 2015–2026 segellat. Mapping M15 PASS_RESEARCH; costos 8/15/30 bps i economia 200 USDC congelats. Només discovery autoritzada, encara no SQCLI/paper. |
| 2026-08-10 | **XAU v36 bloquejada per cobertura abans de discovery vàlida**: només 855/2.022 i 859/2.023 sessions (42,3%/42,5%) tenen tota la ruta M15 completa; 2007–2010 queden especialment mutilats. Un càlcul local havia arribat a mètriques abans de detectar el gate absent: 0 supervivents formals, però queda invalidat i prohibit com a input. No es canvia font/split ni es rescata la família; cadena terminal BLOCK, futurs intactes, no SQCLI. |
| 2026-08-10 | **Metodologia Alquímia v4 cablejada**: cobertura abans de rendiment (≥90% global, ≥80% cada període), mapping/economia/hash/futurs obligatoris. Separa screen determinista de generació SQ: els IDs d'estratègia neixen només a `sq_generation` i requereixen hashes SQ. Control sintètic de 9 etapes complet però no promocionable; v3 continua compatible. US500+VIX haurà d'usar v4. |
| 2026-08-10 | **Runner v4 reprenable implementat**: manifest i commands congelats per hash, una etapa per invocació, lock, timeout, logs limitats/redactats, artefacte pending i chain/latest atòmics. Una fallada conserva la cadena; REJECT/BLOCK impedeix arribar a SQ. Set proves cobreixen ordre, terminalitat, retry, manifest alterat, artefacte invàlid, secrets/logs i 9 checkpoints complets. Frontera CLI/JSON preparada per futura web. |
| 2026-08-10 | **US500 D1 passa mapping v4 sense rendiment**: sessió regular NY 09:30–16:00, 77 dies complets alineats, cobertura comuna 97,47%, correlació close-to-close 0,99881, direcció 100% i diferència close p95 10,34 bps. M15 continua sota el 0,99 exigit i no es rescata. Inputs fixats per SHA-256; recerca US500+VIX segueix bloquejada fins tres dies complets de costos Ostium. |
| 2026-08-10 | **US500 D1 passa cobertura v4 només des de 2018**: l'etiqueta 2012–2026 amagava 16,5%/22,2%/39,8% de cobertura el 2012–2014 i 65,4% el 2017. La política performance-blind selecciona el sufix contigu 2018–08/07/2026: 2.088/2.223 sessions, 93,93% global i mínim anual 89,27%. Els anys incomplets queden prohibits; cap retorn o PnL consultat. |
| 2026-08-10 | **Compositor preflight US500 D1 v4 preparat**: uneix cobertura, mapping, timing VIX i costos per fitxers amb SHA-256. Falta o inconsistència produeix BLOCK sense valors substitutius. Fins i tot amb PASS només autoritza `hypothesis_screen`; SQCLI, paper i live romanen falsos. La configuració estable permet obrir el gate automàticament sense editar-la quan `costs_latest.json` quedi congelat. |
| 2026-08-10 | **Cadena US500 raw→preflight automatitzada**: cada tick del cron executa collector → resum → costos 200 USDC → preflight v4, en aquest ordre i amb sortides atòmiques. `market_preflight_latest.json` mostrarà les causes de BLOCK i passarà sense intervenció només si totes les evidències congelades compleixen; no inicia SQCLI. |
| 2026-08-10 | **Contracte v4 endurit contra PASS nominal**: `hypothesis_screen` ara ha de demostrar ≥50 trades, PF≥1,20, ≥2 veïns estables, tres costos exactes, futurs segellats i ≤5.000 intents; SQ ≤10.000 intents. El validador impedeix crear una metodologia futura debilitant OOS, Monte Carlo, liquidació, risc, marge, reserva o economia del compte de 200 USDC. |
| 2026-08-10 | **Leverage màxim segur convertit en prova**: v4 avalua 1–100x fins al límit Ostium, tria el valor segur més alt i exigeix justificació per cada nivell superior. Recalcula nocional, col·lateral, marge, reserva i risc al stop; exigeix stop, liquidació exacta Ostium i buffer liquidació/stop ≥1,5. Apalancar més no pot saltar risc≤1,5%, marge≤35% ni reserva≥40%. |
| 2026-08-10 | **Filiació screen→SQ obligatòria**: la generació v4 queda fixada a evolució genètica, ≤10.000 intents i 1–3 regles per candidat. Cada `.sqx` conserva hash i hipòtesi font; la cadena rebutja candidats que no descendeixin d'una hipòtesi aprovada, encara que les seves mètriques siguin millors. |
| 2026-08-10 | **Pitjor candidat, no mitjana favorable**: screen, OOS i robustesa v4 exigeixen mètriques per hipòtesi/candidat i recalculen els agregats com el pitjor cas. NaN, infinits i probabilitats fora de rang bloquegen. Abans de sizing la campanya es redueix a un candidat; una futura cartera de 4–8 peces combinarà només cadenes individuals aprovades. |
| 2026-08-10 | **Hashes SQ/IR verificats contra fitxers reals**: v4 ja no accepta un SHA declarat. La cadena obre cada `.sqx`, el `.sqx` traduït i l'IR Python, resol paths relatius a l'artefacte i recalcula SHA-256. Absència o manipulació invalida generació/traducció abans de paritat; controls v3 continuen compatibles. |
| 2026-08-10 | **Paritat i paper deixen de ser booleans**: v4 exigeix informe de paritat i configuració paper JSON hashats, i contrasta candidat/mètriques amb l'artefacte. Paper només passa amb 200 USDC, `mode=paper`, live fals i signer desactivat; un JSON maliciós amb hash correcte també queda rebutjat pel contingut. |
| 2026-08-10 | **Constructor SQ compatible i fail-closed amb v4**: s'ha eliminat la dependència errònia de `discovery` i ara usa `hypothesis_screen`. V4 rebutja random search, pressupost absent o >10.000; exigeix `genetic-evolution`. El stage SQ verifica també manifest hashat, metodologia, pressupost, hash CFX, capital 200 i holdout segellat. V1–v3 mantenen compatibilitat. |
| 2026-08-10 | **Ingestor SQX real per `sq_generation` v4**: deriva del fitxer real ID, SHA-256, suport de traducció i nombre de condicions long/short; la complexitat és el màxim per direcció i queda limitada a 3. Verifica CFX/manifest genètic, pressupost, mercat/timeframe, databank congelat i futurs segellats. La cadena reobre els SQX i detecta mètriques declarades manipulades. 539 tests + 19 subtests PASS. US500 continua BLOCK exclusivament fins congelar tres sessions completes de costos Ostium; encara no s'ha definit ni provat cap regla VIX. |
| 2026-08-10 | **Final d'SQ provat pel watchdog, no declarat a mà**: `sq_generation` deriva els intents del snapshot final hashat (`ATTEMPT_BUDGET`, `ACCEPTED_TARGET` o `WALL_TIME_BUDGET`) i exigeix el mateix projecte del manifest. Inventaria `.sqx` recursivament i lliga rutes/hashes al snapshot; la verificació posterior detecta fitxers afegits, retirats o modificats i intents adulterats. |
| 2026-08-10 | **Traducció SQX→IR Python v4 feta fail-closed**: eliminats del perfil genèric els blocs sense semàntica Python provada (`Highest/Lowest/ADX`, Bollinger, STDDEV, `Not`, inclusius i Open); ROC també exigeix close canònic. Extractor i runtime coincideixen en 21 nodes. El rebut es genera amb l'IR, no obre holdout, lliga el candidat al SQX i la cadena recomputa el JSON canònic; un IR arbitrari hashat ja no passa. La paritat SQ↔Python continua obligatòria abans de paper. |
| 2026-08-10 | **Paritat v4 recalculable des de traces**: SQ i Python han d'aportar traces congelats amb UTC, candles, senyals i trades. Gate: ≥30 senyals/trades coincidents, match 100%, candles ≥95%, correlació PnL ≥0,99, MAE ≤0,005 USDC i error màxim ≤0,01 USDC. La cadena reobre els dos fitxers i recalcula; zero/una operació, PnL escalat o report v2 adulterat no poden passar. V1 queda només per control sintètic de cablejat. |
| 2026-08-10 | **Holdout final convertit en etapa real**: v4 passa de 9 a 10 etapes. Després de robustesa i economia queda un únic candidat congelat i s'obre una sola vegada el 10% final; traducció/paritat/paper ja no declaren accés. Trace hashat de ≥20 trades amb costos base/conservador/estrès; es recalculen PF≥1,10, EV≥0,10 USDC i DD≤20% sobre capital 200. Retuneig, segona avaluació, PF no estimable o resum manipulat fallen i el rebuig és terminal. |
| 2026-08-10 | **Paquet paper lligat a tota la cadena v4**: config schema v2 incorpora exactament pair Ostium, leverage/nocional/col·lateral, risc/marge/reserva/stop aprovats, IR i paritat. Recalcula hashes i exigeix mateixa campanya/candidat; `evidence_chain` compara les cinc fonts amb els rebuts reals previs. No permet augmentar leverage després del gate ni substituir un fals PASS. Continua sense signer, ordres o autorització live. |
| 2026-08-10 | **Selecció Pareto situada on hi ha evidència real**: `sq_generation` ja no afirma seleccionar per expectativa/costos/estabilitat que el SQX no aporta; conserva tots els candidats únics, traduïbles i de ≤3 regles. `temporal_validation` rep obligatòriament l'univers SQ complet, aplica els gates OOS i recalcula el front no dominat maximitzant EV neta i finestres positives i minimitzant drawdown. Ometre rivals o promocionar un dominat invalida la cadena. |
| 2026-08-10 | **Validació temporal v4 derivada de traces**: cada candidat aporta trades train i finestres OOS UTC, ordenades i no solapades, amb capital 200, cost base hashat i holdout tancat. El constructor recalcula PF, EV, drawdown, estabilitat i decay, conserva els hashes dels traces i genera el Pareto; el contracte reobre les fonts i detecta PnL, resum o univers manipulat. |
| 2026-08-10 | **Robustesa v4 derivada de simulacions**: per candidat exigeix exactament 1.000 runs, ≥4 veïns a ±10%, trades amb costos 2×, capital 200 i holdout tancat. Recalcula MC rendible ≥70%, veïns rendibles ≥75%, PF estrès ≥1,05 i liquidació ≤0,1%; aquesta deriva de l'excursió adversa i fórmula Ostium, no d'un booleà. Sizing no pot superar el leverage ni canviar el màxim de venue provats. |
| 2026-08-10 | **Economia de 200 USDC derivada de trades**: `small_account_economics` rep tots els supervivents de robustesa i traces base/conservador/estrès de ≥30 trades. Nocional=`capital×risc%/stop%`; leverage només optimitza col·lateral i no infla risc. Recalcula PF≥1,10, EV≥0,10, pèrdua/trade≤3%, marge/reserva/liquidació i selecciona un únic candidat per pitjor EV→PF→ID. Fonts i hashes queden lligats al rebut de robustesa. |
| 2026-08-10 | **Screen pre-SQ v4 derivat d'una graella train**: variant central i veïns aporten trades nets base/conservador/estrès; el constructor compta intents, recalcula PF i només selecciona si central+≥2 veïns tenen ≥50 trades i PF≥1,20 en tots els costos. Topologia falsa, trace manipulat, >5.000 variants o accés a futur/holdout fallen abans de consumir SQCLI. |
| 2026-08-10 | **Preflight v4 recomponible des de fonts**: l'artefacte observat lliga configuració, cobertura, mapping i costos per ruta/hash; el contracte torna a executar el compositor i exigeix igualtat completa. VIX és un input de règim opcional per no imposar-lo a altres mercats, però si existeix continua obligat a anti-look-ahead. Mutar qualsevol font invalida la cadena. |
| 2026-08-10 | **Collector multi-mercat ajustat al seu gate**: EURUSD/GBPUSD/USDJPY/XAUUSD passen de 4 h a 2 h. Amb 12 intents/dia laborable poden assolir ≥30 captures, ≥3 dies i ≥6 hores dins de tres dies complets; l'instal·lador substitueix de manera idempotent la línia antiga i manté lock/read-only. |
| 2026-08-10 | **Pressupost SQ genètic corregit dins del CFX**: detectat que 4 illes × 100 individus × 100 generacions permetien nominalment 40.000 avaluacions malgrat declarar-ne 10.000, i `EvoRestartOnFinish=true` podia repetir l'evolució. El generador v4 ara deriva una forma ≤ pressupost (10.000 → 4×100×25), fixa decimació 1, desactiva els dos reinicis i ho desa al manifest. Transport GUI auditat: canals oficials engine/progress i GET oficial de pause/stop; quan `tasksIterations` no arriba, el watchdog retorna `generated=null` i no inventa evidència. |
| 2026-08-10 | **CFX genètic verificat pel contingut, no només pel hash**: l'ingestor i el contracte final reobren el ZIP, exigeixen un únic Build task segur i recalculen illes×població×generacions. Rebutgen decimació ≠1, reinicis actius, pressupost/manifest discrepants i StopCondition diferent del límit congelat. Els controls sintètics de cablejat queden explícitament exempts i continuen no promocionables. 684 tests + 19 subtests PASS. |
| 2026-08-10 | **Screen→CFX EURUSD automatitzat i reproduïble**: nou `eurusd_v4_project_batch.py` verifica bootstrap i hashes de cada branca, recompila el pla des de cadena+screen, genera i reobre un CFX per hipòtesi i mai inicia SQCLI. ZIP amb metadata canònica i manifest sense rellotge mutable: smoke real doble produeix el mateix SHA-256 per CFX i manifest. |
| 2026-08-10 | **Errata experimental del pressupost genètic SQ**: smoke aïllat 4×25×1 nominal=100 acaba en 32 s amb 192 generades, 10 acceptades i 182 rebutjades; 104 rebuigs són d'initial population. `tasksIterations=1` era generació, no intents. Evidència/log hashats; candidats prohibits i projecte disposable eliminat. Watchdog corregit: `totalJobsDone` com a lower bound viu, log `Strategies generated` com a final exacte; sense log hashat no hi ha rebut v4. |
| 2026-08-10 | **Importació CFX→SQCLI separada de l'inici**: `sqcli_import_batch.py` valida el lot complet i col·lisions, importa via protocol GUI oficial, reexporta el CFX reserialitzat, torna a verificar els camps científics i exigeix recursos resolts. Smoke real PASS amb hashes font/importat esperats i `sqcli_started=false`; projecte disposable eliminat després. |
| 2026-08-10 | **Llançament SQ supervisat i reserva reactiva, smoke real PASS**: v4 congela 64 intents de reserva (parada live a 9.936 per una cota dura de 10.000) per absorbir treballs en vol. `sqcli_supervised_run.py` només inicia un projecte procedent d'un rebut d'importació hashat, exigeix SQ globalment inactiu i databank net, i conserva preflight, journal, estat i log final. Una finalització natural es detecta; tres errors consecutius de monitoratge provoquen parada fail-safe. Smoke disposable nominal 100: control a 40, final exacte 40 (0 acceptats), versus 192 sense reserva; dins la cota, però candidats prohibits. 708 tests + 19 subtests PASS. |
| 2026-08-11 | **`sq_generation` reprenable de punta a punta**: `sq_generation_stage_v4.py` deriva CFX/manifest/databank exclusivament de batch→rebut d'importació, inicia o reprèn el llançador i construeix l'artefacte observat. Preflight i start tenen rebuts durables; repetir una execució completa és idempotent i una interrupció no inicia SQ dues vegades. L'artefacte lliga CFX font i CFX reserialitzat executat. Zero SQX ja és `REJECT` terminal amb log/pressupost, no un fals error infinit. Esquema runner corregit a les 10 etapes incloent holdout. 713 tests + 19 subtests PASS. |
| 2026-08-11 | **Importació batch SQCLI reprenable**: cada projecte rep `IMPORT_INTENT` durable abans de mutar SQ i `VERIFIED` només després de reexportar i reobrir el CFX. Una caiguda entre open/export es reprèn contra el projecte propi; una col·lisió sense intent continua fallant tancada. Repetir un rebut complet valida batch, checkpoint, CFX i recursos sense mutació Docker. El llançador rebutja checkpoints incomplets o manipulats. |
| 2026-08-11 | **Trace temporal derivat de l'export SQ**: `sq_temporal_trace_v4.py` transforma `orders.csv` + split canònic en trades train i finestres anuals validation/OOS, recalculant retorn long/short i durada. Rebutja holdout, trades entre segments i DST ambigu. `temporal_validation` reconstrueix el trace des de les fonts hashades i detecta edició del CSV/JSON. En aquest punt encara faltava el Retest supervisat; queda resolt a l'entrada següent. |
| 2026-08-11 | **Retest pre-holdout supervisat implementat i smoke real PASS**: `alquimia_retest.py` produeix CFX reproduïble train+validation+OOS per un SQX exacte, sense gates de rendiment ni eliminació de fallits. `sqcli_supervised_retest.py` sincronitza input/output explícitament, exigeix 1 input/1 output/1 test al log, espera SQX estable, valida `orders.bin` i exporta CSV oficial. Smoke XAU: 987 ordres 2017-01-04→2025-07-28, holdout intacte i rebut reconstruït. És prova operativa, no candidat: falta cost XAU v4 compatible. Pendent integrar-lo al runner de campanya. |
| 2026-08-11 | **Adaptador temporal per campanya**: `sq_temporal_stage_v4.py` consumeix exclusivament l'artefacte `sq_generation` promocionable, reobre identitat/hash de cada SQX, genera o reprèn un Retest supervisat per candidat, deriva el trace lligat al rebut i construeix l'artefacte Pareto temporal. Manté separats manifest de dates SQ i contracte temporal canònic. Pendent executar-lo amb candidats nous i un cost model v4 compatible amb el mercat. |
| 2026-08-11 | **Univers SQ multi-branca abans del Pareto**: `sq_generation_universe_v4.py` verifica totes les branques terminals, conserva la procedència incloses les branques sense candidats, reobre els SQX i produeix una única entrada immutable per al Retest temporal. Només deduplica estratègies byte-a-byte idèntiques i rebutja col·lisions de `StrategyName`; el worker EURUSD ja en segella ruta i hash. Així la selecció Pareto serà global, no tres seleccions locals esbiaixades. |
| 2026-08-11 | **Continuació EURUSD SQ→Pareto automatitzada**: `eurusd_v4_temporal_worker.py` consumeix només el rebut global promocionable, deriva de fonts hashades costos Ostium, split temporal, manifest i recurs EURUSD, espera SQ aliè i reprèn únicament un Retest propi checkpointat. Comparteix cron i `flock` amb el generador, manté holdout tancat i paper/live falsos. Smoke operatiu actual: `WAITING_FOR_SCREEN`→`WAITING_FOR_SQ_GENERATION`, sense iniciar SQ. |
| 2026-08-11 | **Pareto→robustesa EURUSD automatitzat**: `eurusd_v4_robustness_worker.py` només consumeix un Pareto temporal PASS, exigeix metodologia i costos congelats per hash, deriva el cap EUR/USD del mínim de ≥30 observacions Ostium i executa Monte Carlo natiu sota el mateix `flock`. `overnightMaxLeverage=0` només es tracta com absència de l'override d'accions quan `category=forex`; qualsevol altra semàntica falla tancada. Una branca temporal REJECT no inicia SQ i un MC propi checkpointat és l'únic projecte actiu que pot reprendre. |
| 2026-08-11 | **Robustesa→sizing 200 USDC automatitzat**: contracte complet de 5.884 sessions EURUSD NY-17 (2003-05-05→2026-02-26), cobertura i OHLC SQ↔font D1 Dukascopy 100%. `eurusd_v4_small_account_worker.py` reobre candles/costos/metodologia/robustesa per hash i calcula stop, nocional, col·lateral, reserva, costos i liquidació trade a trade. La selecció no pot superar el leverage que va aprovar Monte Carlo. La cadena cron queda `screen→SQ→Pareto→robustesa→small-account`, holdout encara tancat. |
| 2026-08-11 | **Probe real SQ→Python i paritat completa PASS**: JAR de probe determinista i aïllat sobre SQ 143.2708 registra les quatre variables per barra; 2.684 barres/10.736 valors validats. Corregits gates compostos (`short AND NOT long`), semàntica Java exacta d'`IsRising/IsFalling`, warm-up 2003 i `DontTradeOnWeekends`. EURUSD D1 coincideix en 2.255/2.255 senyals i 86/86 trades, corr. PnL 0,999999994 i error màxim 0,00091 USDC a nocional 200; artefacte formal PASS. El candidat és només prova tècnica i continua descartat per rendiment. SQCLI normal restaurat i saludable; 783 tests + 19 subtests PASS. |
| 2026-08-11 | **Robustesa nativa orquestrada**: `sq_robustness_stage_v4.py` consumeix només el Pareto temporal, exigeix costos Ostium `PASS_COSTS_FROZEN`, executa i supervisa 1.000 variants paramètriques natives d'SQ, exporta amb checkpoints, combina-les amb 1.000 bootstraps preregistrats i escaneja la graella d'apalancament de dalt a baix. El contracte verifica per fonts que el leverage seleccionat és el màxim que passa robustesa i liquidació. Controls: 749 proves + 19 subproves; execució real pendent de 30 mostres/3 dies de costos. |
| 2026-08-11 | **Rebuig temporal sense perdre el lot**: zero trades, zero OOS o train no positiu són ara mètriques conservadores amb `temporal_eligibility_failure`, no excepcions. L'artefacte `REJECT` conserva i reobre tots els traces i recomputa Pareto buit sense agregats inventats. Errors de provenance, esquema o holdout continuen fallant tancats. |
| 2026-08-11 | **Sizing real per operació per a 200 USDC**: la traça temporal conserva timestamp/preu d'entrada i unitats SQ; `small_account_trace_v4.py` reobre el SQX del Retest i reconstrueix el stop inicial ATR de la barra anterior o percentatge fix per cada trade. `sq_small_account_stage_v4.py` deriva nocional, costos, col·lateral, reserva i buffer de liquidació per operació, i selecciona el leverage segur màxim sense inflar el risc. Un nou contracte hashat exigeix ≥95% de cobertura i coincidència OHLC SQ↔Dukascopy abans d'usar les candles. Cap stop o nocional manual pot promocionar. |
| 2026-08-11 | **Captura de costos accelerada sense relaxar el gate**: el cron read-only d'EURUSD/USDJPY/GBPUSD/XAUUSD passa de cada dues hores a cada hora laborable. Conserva `flock`, snapshots raw/normalitzats, 11 nocionals i els mínims independents de 30 mostres, 3 dies i 6 hores UTC. Estat inicial: FX 8/30 i XAU 7/30; l'horitzó inferior passa d'~44 h a ~22 h de captures disponibles. |
| 2026-08-11 | **Holdout final natiu, únic i uncensored**: `sq_final_holdout_stage_v4.py` només obre el 10% segellat després d'un únic PASS de 200 USDC. Congela un intent per candidat, genera SQ sense filtres ni eliminació de fallits, supervisa exactament 1 input/1 output i registra `holdout_evaluation_count=1`. La traça reobre orders/SQX/candles i reconstrueix stop ATR per trade; nocional=`min(200×1,5%/stop%,cap pre-holdout)`. Zero trades o PF no estimable es conserva com REJECT terminal, mai com excusa per reobrir el holdout. |
| 2026-08-11 | **Traducció lligada al guanyador del holdout**: `sq_python_translation_stage_v4.py` rebutja REJECT, segona avaluació o traça no reproduïble; només tradueix el SQX exacte hashat que ha passat l'únic holdout. El contracte de cadena reobre també l'artefacte final i n'exigeix campanya/candidat/PASS. Auditoria de paritat: `orders.csv` no prova tots els senyals inhibits; la via oficial de Custom Analysis és post-backtest i encara requereix un probe real de logging per barra. |
| 2026-08-11 | **Stage de paritat probe→runner v4 implementat**: el supervisor de Retest inspecciona JAR read-only, variable/mount de log i rebutja raw preexistent; el rebut final lliga el log a l'execució. `sq_parity_stage_v4.py` reobre el guanyador traduït, Retest, normalització, warm-up Dukascopy, senyals i traces a 200 USDC. Un bundle hashat és obligatori per a `PASS` nadiu; alterar raw log o qualsevol font invalida la cadena. 787 tests + 19 subtests PASS. Queda automatitzar el cicle de vida Docker del contenidor aïllat dins l'orquestrador operatiu. |
| 2026-08-11 | **Cicle Docker del probe automatitzat i recuperable**: `sq_signal_probe_controller.py` journalitza abans d'aturar SQ normal, executa el JAR hashat amb `internal` read-only i tmpfs temporals, reprèn una captura interrompuda i només restaura després del Retest verificat. Smoke Docker real start→status→restore: SQCLI normal actiu, probe absent, 71 projectes visibles i cap execució. Els errors Docker fallen tancats i una regressió cobreix permisos vs contenidor absent. 794 tests + 19 subtests PASS. |
| 2026-08-11 | **Trigger immutable costos→screen EURUSD**: el collector horari invoca `eurusd_v4_screen_trigger.py`; en BLOCK és read-only i no inicia SQCLI. Al primer PASS journalitza i congela costos, cobertura, mapping, recurs SQ, CSV i metodologia abans de mirar train, recompòn el preflight sobre les còpies i executa una sola vegada les 9 variants preregistrades. Pot reprendre interrupcions; repeticions reobren també traces, artefactes, cadenes i plans, encara que els `latest` continuïn canviant. Smoke real actual: `WAITING_FOR_MARKET_PREFLIGHT`, zero estat creat. 800 tests + 19 subtests PASS. |
| 2026-08-11 | **Preparació SQ multi-branca recuperable**: `eurusd_v4_project_batch.py` té checkpoint `VERIFIED` per hipòtesi, reprèn una branca parcial i revalida els CFX finals sense reconstruir-los. El rebut lliga també registre Ostium i metodologia, no només bootstrap/scaffold. `sqcli_import_batch.py` rebutja qualsevol importació nova si hi ha un projecte SQ actiu, abans de tocar Docker. Pendent: worker separat perquè una generació llarga no bloquegi el collector de costos. |
| 2026-08-11 | **Worker SQ EURUSD separat implementat**: `eurusd_v4_sq_worker.py` espera el screen, congela i audita el scaffold SQ 143.2708 com a format XML pur, compila/importa amb checkpoints i executa seqüencialment només amb SQCLI lliure. Una represa només tolera com a actiu el projecte propi declarat al journal. Cron independent cada 10 minuts amb `flock` propi, sense bloquejar captures. Smoke real abans de maduresa: `WAITING_FOR_SCREEN`, zero estat i zero Docker. |
| 2026-08-11 | **Scaffold neutralitzat quantitativament**: l'auditoria va trobar valors antics heretats (genètica 93/30, RSI 39–63, ROC −0,25–0,26, exit 2–48). Ara metodologia v4 fixa 80/20, migració 5/10 i rangs per breakout/momentum/shock; el constructor força Close-only, elimina presets, uniformitza pesos i reescriu thresholds/sortides. Smoke sobre els tres CFX reobert pel contracte: 10.000 avaluacions exactes i recurs `EURUSD_ALQ_NY17_D1` D1 UTC correcte; cap importació executada. 811 tests + 19 subtests PASS. |
