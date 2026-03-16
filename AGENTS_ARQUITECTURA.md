# AGENTS_ARQUITECTURA.md — TradingAgent

**Data:** 2026-03-16
**Repo/Path:** `/mnt/volume-SQ/dev/TradingAgent`
**Modes:** PAPER / LIVE / STOPPED
**Timeframe operatiu:** 1H
**Assets MVP:** ETHUSDT, BTCUSDT, SOLUSDT
**Objectiu:** Bot de trading que consumeix BrokerageService per operar a Ostium amb estratègies automatitzades.

---

## 0) TL;DR

- **TradingAgent és el cervell**: decideix QUÈ i QUAN operar
- **BrokerageService és el cos**: executa ordres, serveix dades, gestiona posicions
- Comunicació via HTTP (gateway BS :8081, hostname Docker `datalayer-proxy`)
- 2 background loops: `poll_loop` (5min) + `close_loop` (30s)
- Persistència SQLite: signals, trades, equity, agent_state
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
| Leverage | 100x |
| Nominal | col × leverage |
| Fee estimada | 3.36$/trade |
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

## 9) Fases d'implementació

### MVP
- `float`, 2 loops, `runtime/engine.py` mínim
- `agent_state` persistent, `close_due_at` persistent
- Reconciliació mínima inline (dins close_loop)
- Tests purs estil BS
- 1 estratègia: Capitulation Scalp 1H
- Paper + Live executors

### V1
- `recovery.py` formal
- `pending_actions` taula
- Reconcile loop separat
- Contract tests del LiveExecutor
- Quality gating estricte
- Mètriques/telemetria

### V2
- Multi-strategy + allocation engine
- AI Agent Orchestrator (Claude API)
- Web UI

---

## 10) Docker

```yaml
# docker-compose.yml
services:
  trading-agent:
    build: ./docker
    container_name: trading-agent
    environment:
      - BS_BASE_URL=http://datalayer-proxy:8081
      - MODE=paper
      - SYMBOLS=ETHUSDT,BTCUSDT,SOLUSDT
      - POLL_INTERVAL_S=300
      - CLOSE_CHECK_INTERVAL_S=30
      - CAPITAL_INITIAL=250
    volumes:
      - ./data:/app/data     # SQLite
      - ./lab:/app/lab
      - ./strategies:/app/strategies
    ports:
      - "8090:8090"
    networks:
      - brokerage_net

networks:
  brokerage_net:
    external: true
```

---

*Generat: 2026-03-16*
