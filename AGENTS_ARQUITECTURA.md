# AGENTS_ARQUITECTURA.md — TradingAgent

**Data:** 2026-03-16
**Repo/Path:** `/mnt/volume-SQ/dev/TradingAgent`
**Modes:** PAPER / LIVE / STOPPED
**Timeframe operatiu:** D1 (paper probe T7) → 1H crypto (futur)
**Assets paper probe:** MSFT (primari), NVDA, QQQ
**Assets futur:** ETHUSDT, BTCUSDT, SOLUSDT + equitats Ostium
**Setup actiu:** `capitulation_d1` (body<-2% + BB_lower D1)
**Objectiu:** Bot de trading paper (T7) i futur live que opera a Ostium amb estratègies automatitzades.

---

## 0) TL;DR

- **TradingAgent és el cervell**: decideix QUÈ i QUAN operar
- **BrokerageService és el cos**: executa ordres, serveix dades, gestiona posicions (futur live)
- **T7 paper probe**: `DailyEngine` (1 cop/dia post-close) + yfinance D1 feed + SQLite
- Comunicació futura via HTTP (gateway BS :8081, hostname Docker `datalayer-proxy`)
- Loops futurs: `poll_loop` (5min, candles 1H) + `close_loop` (30s, settlements)
- **Ara**: `DailyEngine` (1 cop/dia D1) + `YFinanceD1Feed`
- Persistència SQLite: signals, paper_trades, agent_state
- Paper mode automàtic: 2 losses → paper fins que 1 senyal guanyi

---

## 1) Diagrama de components

```
┌───────────────────────────────────────────────────────────┐
│                      TradingAgent                          │
│                                                            │
│  ┌────────────┐    ┌───────────┐    ┌──────────────┐      │
│  │   Market    │───>│  Strategy  │───>│     Risk     │      │
│  │  Monitor    │    │   Engine   │    │   Manager    │      │
│  │            │    │            │    │              │      │
│  │ poll 1H    │    │ entry()    │    │ paper/real   │      │
│  │ BB,RSI,    │    │ score 0-8  │    │ sizing       │      │
│  │ drop,vol   │    │ MFE/MAE    │    │ 1 pos max    │      │
│  └────────────┘    └───────────┘    └──────┬───────┘      │
│                                             │              │
│                                   ┌─────────▼──────────┐  │
│                                   │ Execution Bridge    │  │
│                                   │ Paper | Live        │  │
│                                   └─────────┬──────────┘  │
│                                             │              │
│  ┌──────────────────┐    ┌─────────────┐    │              │
│  │ Portfolio Tracker │<───│   Runtime    │<───┘              │
│  │ SQLite            │    │   Engine    │                   │
│  └──────────────────┘    │ 2 loops     │                   │
│                           └─────────────┘                   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP (httpx async)
                  ┌────────────▼─────────────┐
                  │   BrokerageService :8081   │
                  │   /realtime/* (candles)    │
                  │   /trade/*   (ordres)      │
                  └──────────────────────────┘
```

---

## 2) Flux operatiu

### poll_loop (cada 5 min)

```
1. Per cada símbol (ETH, BTC, SOL):
   GET /realtime/ohlcv/{symbol}?tf=1h&limit=200
2. Validar qualitat: is_complete, count >= 25, X-Data-Missing-Minutes
3. Si nova candle tancada (ts ha canviat):
   a. Actualitzar ring buffer (200 candles)
   b. Calcular indicadors: BB(20,2), RSI(7), drop_3h, vol_rel
   c. Per cada strategy activa:
      - evaluate(asset, indicators) → Signal | None
      - Si Signal: persistir a signals
   d. Risk Manager: check posicions, mode, sizing
      - Si aprovat: crear TradePlan
   e. Execution: PaperExecutor o LiveExecutor
      - Paper: registrar trade pending_settlement
      - Live: POST /orders/open → guardar operation_id
```

### close_loop (cada 30s)

```
1. Buscar trades amb status in ('submitted', 'open')
2. Si 'submitted' live:
   - GET /positions → si posició apareix → marcar 'open'
3. Si close_due_at <= now:
   - Paper: resolver amb candle (entry=open, exit=close, pnl=...)
   - Live: POST /orders/close
4. Actualitzar trade, equity_snapshot, agent_state
5. State machine: on_trade_closed(pnl)
   - Si pnl < 0: consec_losses++
   - Si consec_losses >= 2 i mode==REAL → switch PAPER
   - Si mode==PAPER i trade paper guanyador → switch REAL
```

---

## 3) State machine del Risk Manager

```
         ┌──────────────────────┐
         │       REAL           │
         │  (opera amb capital)  │
         └──────────┬───────────┘
                    │ 2 losses consecutives
                    ▼
         ┌──────────────────────┐
         │       PAPER          │
         │  (simula, no opera)   │
         └──────────┬───────────┘
                    │ 1 senyal paper guanyador
                    ▼
         ┌──────────────────────┐
         │       REAL           │
         └──────────────────────┘

         Qualsevol → STOPPED si capital < 100$
         STOPPED requereix intervenció manual (POST /mode/live)
```

---

## 4) Comunicació amb BrokerageService

### Candles
```
GET /realtime/ohlcv/{symbol}?tf=1h&limit=200
→ {candles: [{ts, open, high, low, close, volume}], count, is_complete}
Headers: X-Data-Source, X-Data-Missing-Minutes, X-Data-Max-Gap-S
```

### Obrir posició (async, fast-ack)
```
POST /trade/api/v1/broker/orders/open
{venue: "ostium", symbol, side: "long", collateral, leverage, client_order_id}
→ 202 + {operation_id}
```

### Tancar posició
```
POST /trade/api/v1/broker/orders/close
{venue: "ostium", position_id, percent: 100, client_close_id}
→ 200 | 202
```

### Consultes
```
GET /trade/api/v1/broker/positions?venue=ostium
GET /trade/api/v1/broker/balance?venue=ostium
GET /trade/api/v1/broker/operations/{operation_id}
```

---

## 5) Persistència SQLite (4 taules)

### signals
Tots els senyals detectats, inclosos rebutjats.
```
id, created_at, candle_ts, asset, strategy, direction, score,
expected_mfe, expected_mae, body_pct, bb_lower, rsi_7, drop_3h_pct, vol_rel,
quality_accepted, quality_reason, accepted_by_risk, rejection_reason, mode
```

### trades
Només senyals aprovats que s'han executat (paper o real).
```
id, signal_id, asset, strategy, mode, status,
requested_at, opened_at, closed_at, close_due_at,
position_id, entry_price, exit_price,
collateral, leverage, nominal, fee, pnl, pnl_pct,
score, paper_mode_reason, last_error
```

### equity_snapshots
Cada hora + després de cada trade close.
```
timestamp, capital, unrealized_pnl, drawdown_pct, mode
```

### agent_state
Key/value JSON, una fila per clau.
```
key, value_json, updated_at
```
Claus: `runtime_state` (mode, consec_losses, open_trade_id, stop_reason),
`last_seen_candle_by_symbol` ({ETH: ts, BTC: ts, SOL: ts})

---

## 6) Sizing i regles operatives

| Paràmetre | Valor |
|-----------|-------|
| Col·lateral | min(max(capital × 20%, 15$), 60$) |
| Leverage | **20x** (T1: recalibrat amb liquidació simulada, era 100x) |
| Nominal | col × leverage (ex: 40$ × 20 = 800$) |
| Fee estimada | 5.38$/trade (Ostium, validat T6d) |
| Max posicions | 1 simultània |
| Stop Loss | Cap (el rebot necessita espai) |
| Exit | Close de la candle 1H (hold 1h) |
| Paper trigger | 2 pèrdues consecutives |
| Paper exit | 1 senyal paper guanyador |
| Stop total | Capital < 100$ |

---

## 7) Quality gating (MVP)

- `is_complete == true` → obligatori
- `count >= 25` → obligatori (per BB20 + RSI7)
- `X-Data-Missing-Minutes > 0` → warning (log, no bloqueja MVP)
- `X-Data-Max-Gap-S > 3600` → rebutjar candle

---

## 8) Recovery a startup (MVP mínim)

1. Carregar `agent_state` de SQLite
2. `GET /trade/api/v1/broker/positions?venue=ostium`
3. Si BS reporta posició oberta:
   - Vincular amb trade local `status=open` si existeix
   - Si no existeix → log warning, crear registre de reconciliació
4. Si trade local `status=submitted` sense posició al BS:
   - Verificar uns cicles → si no apareix, marcar `failed`
5. Reprendre `close_due_at` per trades oberts

---

## 9) Gate de producció

> **TradingAgent no entrarà en fase BUILD/producció mentre l'estratègia activa no presenti
> una expectativa de rendibilitat considerada suficient pel projecte.**

### Criteri mínim per autoritzar BUILD

- EV/trade > 0 amb liquidació simulada ✓ (actual: +5.6$)
- MC validation PASS ✓ (3/3)
- Walk-forward PASS ✓ (7/9)
- **Decisió explícita del projecte** que el cas econòmic justifica la inversió en codi

### Estat actual: **PAPER PROBE — T7 en curs**

LAB tancat (T6→T6g). Troballa definitiva:
- **MSFT** `capitulation_d1`: WR 78%, EV +12.7$/t, liq 0%, WF 10/12 → **ACCEPTED_D1_ASSET**
- **NVDA**, **QQQ**: WATCHLIST complementaris
- **CAGR simulat**: 15-25% (fixed col_max) / 25-53% (compounding)

Paper probe autoritzat (T6e: `PAPER_PROBE_AUTHORIZED`).
T7 implementat: `DailyEngine + PaperExecutor + SQLite + FastAPI`. Tests 7/7 PASS.

**Pròxim**: ≥4 setmanes paper → T8 decisió live.

---

## 10) Fases d'implementació (condicional a §9)

### LAB (actual)
- Exploració d'estratègies
- Validació MC + WF + stress test
- Decisió go/no-go per cada estratègia candidate

### BUILD MVP (quan §9 autoritzat)
- `float`, 2 loops, `runtime/engine.py` mínim
- `agent_state` persistent, `close_due_at` persistent
- Reconciliació mínima inline (dins close_loop)
- Tests purs estil BS
- Paper + Live executors

### PAPER (4 setmanes mínim)
- Bot operant en paper mode real
- Comparar resultats vs backtest
- Validar integració BS

### GO-LIVE
- Revisió resultats paper vs expectativa
- Capital limitat inicial
- Monitoring actiu

### V1 (robustesa post-live)
- `recovery.py` formal, `pending_actions`, reconcile loop
- Contract tests, quality gating estricte, mètriques

### V2 (creixement)
- Multi-strategy + allocation engine
- AI Agent Orchestrator (Claude API)
- Web UI

---

## 11) Docker

```yaml
# docker-compose.yml (T7 paper probe D1)
services:
  trading-agent:
    build: ./docker
    container_name: trading-agent
    environment:
      - PROBE_ASSETS=MSFT,NVDA,QQQ
      - LEVERAGE=20
      - CAPITAL_INITIAL=250
      - FEE=5.38
      - DB_PATH=/app/data/paper_probe.db
      - DATA_LOOKBACK_DAYS=365
    volumes:
      - ./data:/app/data     # SQLite
      - ./lab:/app/lab
    ports:
      - "8090:8090"
    # (futur live: afegir BS_BASE_URL + brokerage_net)

# Futur live:
#   - BS_BASE_URL=http://datalayer-proxy:8081
#   - SYMBOLS=ETHUSDT,BTCUSDT,SOLUSDT
#   networks: brokerage_net (external: true)
```

---

## 12) Decisió T1: Leverage recalibrat (2026-03-16)

El stress test va revelar que **leverage 100x = 61% liquidacions** (MAE mediana 1.50%, liq threshold 1%).
Backtest refet amb liquidació simulada (si MAE >= 1/leverage → pnl = -collateral):

| Lev | Liq% | WR | PF | EV/trade | 250$→ | MaxDD | Anys +/- |
|-----|------|-----|-----|----------|-------|-------|----------|
| 10x | 5% | 56% | 1.3 | +2.0$ | 560$ | 28% | 3+/6- |
| **15x** | **9%** | **59%** | **1.4** | **+4.3$** | **924$** | **23%** | **5+/5-** |
| **20x** | **14%** | **59%** | **1.4** | **+5.6$** | **1.114$** | **37%** | **5+/5-** |
| 30x | 24% | 58% | 1.5 | +9.2$ | 1.596$ | 28% | 5+/5- |
| 50x | 38% | 50% | 1.7 | +16.4$ | 2.369$ | 17% | 8+/2- |
| 100x | 68% | 21% | 0.7 | -7.1$ | 10$ | 98% | 0+/3- |

**Decisió MVP: 20x**
- Criteri: max EV amb liquidació ≤20% i MaxDD ≤60%
- Runner-up: 15x (menys DD 23%, menys EV +4.3$)
- EV real: +5.6$/trade × 18t/any = ~100$/any amb 250$
- Script: `lab/studies/leverage_recalibration.py`
- Artifact: `lab/out/leverage_recalibration.json`

---

---

## 13) T7 — Paper Probe D1 (2026-03-16)

### Setup i assets

| Paràmetre | Valor |
|-----------|-------|
| Setup | `capitulation_d1`: body<-2% + close<BB_lower(20,2) |
| Asset primari | MSFT (ACCEPTED_D1_ASSET, WR 78%, EV +12.7$/t) |
| Assets complementaris | NVDA (WR 63%, EV +6$/t), QQQ (WR 63%, EV +3.6$/t) |
| TF | D1 (candles diàries) |
| Entry | open(T+1) | Exit | close(T+1) |
| Leverage | 20x | Col | min(max(cap×20%, 15$), 60$) |
| Liq threshold | MAE ≥ 5% → pnl = −col − fee |

### Components implementats (T7)

| Paquet | Fitxer | Rol |
|--------|--------|-----|
| shared | config.py | Config via env |
| shared | models.py | SignalRecord, PaperTradeRecord, AgentState |
| portfolio | db.py | SQLite: signals, paper_trades, agent_state |
| portfolio | tracker.py | Actualitza capital/pnl/losses |
| strategy | capitulation_d1.py | Detecta senyal |
| market | data_feed.py | yfinance D1 (paper), futur→BS |
| execution | paper.py | PaperExecutor: open+settle+liq |
| runtime | engine.py | DailyEngine: scan+settle+open |
| apps/agent | app.py+routes.py | FastAPI /health /status /signals /trades POST /scan |

### Com arrencar

```bash
mkdir -p data
uvicorn apps.agent.app:app --host 0.0.0.0 --port 8090
curl -X POST http://localhost:8090/scan   # scan manual
curl http://localhost:8090/status
```

### Criteris de sortida T7 (→ T8 decisió live)

- ≥4 setmanes en marxa sense errors crítics
- ≥3 senyals MSFT detectats i registrats
- WR paper coherent amb backtest (78% ± marge estadístic)
- Cap discrepància inexplicada entre senyal i trade paper

*Actualitzat: 2026-03-16 (T7 paper probe implementat)*
