# Prompt per ChatGPT — Disseny arquitectònic TradingAgent

Copia tot el text d'aquest fitxer i enganxa'l a ChatGPT (o4/o3).
Després comparteix el resultat amb Claude per revisar.

---

## PROMPT:

Necessito que em facis un pla arquitectònic complet per a un **nou projecte Python** anomenat **TradingAgent** — un bot de trading automatitzat que consumeix un servei existent (BrokerageService) per operar a **Ostium** (DEX on-chain, crypto perpetual futures).

### El que JA tinc: BrokerageService (producció)

El BrokerageService és un projecte meu en producció, Python 3.11 + FastAPI + asyncio, amb 3 serveis desacoblats via Docker Compose:

- **realtime_datalayer** (port 8082) — grava candles 1m 24/7 des d'Ostium via websocket
- **historical_datalayer** (port 8002) — backfill històric Dukascopy, export
- **trading_service** (port 8010) — broker adapter, execució d'ordres a Ostium, posicions, balance

Gateway Nginx al port **8081** mapeja: `/realtime/*` → 8082, `/data/*` → 8002, `/trade/*` → 8010.

**API que el TradingAgent consumirà (ja implementada i testejada):**

#### Llegir candles:
```
GET /realtime/ohlcv/ETHUSDT?tf=1h&limit=100
→ {candles: [{ts, open, high, low, close, volume}, ...], count, is_complete}

Headers de qualitat: X-Data-Source, X-Data-Missing-Minutes, X-Data-Max-Gap-S
```

#### Obrir posició:
```
POST /trade/api/v1/broker/orders/open
Body: {
  "venue": "ostium",
  "symbol": "ETHUSDT",
  "side": "long",
  "collateral": 40.0,
  "leverage": 100,
  "client_order_id": "cap-scalp-eth-20260315-2000"  // idempotency key
}
→ 202 Accepted + {operation_id}   // async fast-ack, execució en background
```

#### Tancar posició:
```
POST /trade/api/v1/broker/orders/close
Body: {
  "venue": "ostium",
  "position_id": "ostium:12345",
  "percent": 100,
  "client_close_id": "close-eth-20260315-2100"
}
→ 200 | 202
```

#### Consultar posicions:
```
GET /trade/api/v1/broker/positions?venue=ostium
→ {count, positions: [{position_id, symbol, side, collateral, leverage,
    notional, open_price, current_price, unrealized_pnl, unrealized_pnl_percent,
    sl_price, tp_price, open_time}]}
```

#### Consultar balance:
```
GET /trade/api/v1/broker/balance?venue=ostium
→ {usdc, available_margin, used_margin, total_equity, margin_usage_percent}
```

#### Poll operació async:
```
GET /trade/api/v1/broker/operations/{operation_id}
→ {operation_id, status, result: {...}}
```

**Docker**: els serveis corren a la network `brokerage_net`. El TradingAgent s'hi connectarà via hostname `datalayer-proxy:8081`.

---

### Què necessito: TradingAgent

Un projecte **separat** que s'asseu al costat del BrokerageService. El TradingAgent és el **cervell** (decideix QUÈ i QUAN operar). El BrokerageService és el **cos** (executa, dades, posicions).

El TradingAgent **NO** reimplementa res que ja fa el BS. No connecta a Binance, no parla amb Ostium directament, no grava candles. Només consumeix l'API HTTP del BS.

#### Flux principal (loop cada candle 1H):

```
1. Timer s'activa (cada hora en punt, o poll periòdic)
2. Market Monitor:
   - GET /realtime/ohlcv/{symbol}?tf=1h&limit=25  (per cada asset: ETH, BTC, SOL)
   - Calcular indicadors incrementalment: BB(20,2.0), RSI(7), drop_acumulat_3h, vol_relatiu
3. Strategy Engine:
   - Per cada asset, cridar strategy.evaluate(asset, indicators)
   - Si retorna Signal(LONG, score, mfe, mae) → continuar
   - Si None → no fer res
4. Risk Manager:
   - Comprovar: hi ha posició oberta? → si sí, rebutjar (1 pos max)
   - Estem en paper mode? → si sí, simular sense executar
   - Calcular sizing: col = min(max(capital * 20%, 15$), 60$)
   - Circuit breakers: capital < 100$ → stop
5. Execution Bridge:
   - Mode PAPER: registrar trade simulat, esperar 1H, calcular resultat
   - Mode LIVE: POST /trade/api/v1/broker/orders/open al BS
   - Al tancar la candle (1H després): POST /trade/api/v1/broker/orders/close
6. Portfolio Tracker:
   - Registrar trade (real o paper) amb tots els detalls
   - Actualitzar equity curve, drawdown, P&L
   - Avaluar si cal switch paper↔real (paper mode automàtic)
```

#### Funcionalitats MVP

**1. Market Monitor**
- Poll cada 5 minuts (o configurable) → guardar última candle 1H per asset
- Quan detecta nova candle (ts canvia) → trigger evaluation
- Calcular indicadors: BB lower(20,2.0), RSI Wilder(7), drop acumulat 3 candles, volum relatiu (vol / SMA20(vol))
- Buffer circular de 200 candles per asset (per BB i RSI)

**2. Strategy Engine**
- Interfície genèrica:
```python
class IStrategy(Protocol):
    name: str
    def evaluate(self, asset: str, indicators: Indicators) -> Signal | None: ...

@dataclass
class Signal:
    direction: Literal["LONG"]
    score: int          # 0-8
    expected_mfe: float # ex: 0.0524
    expected_mae: float # ex: 0.0427
    strategy: str       # nom de l'estratègia
    asset: str
    timestamp: datetime
```
- Primera implementació: `CapitulationScalp1H` amb les regles:
  - body < -3% AND close < BB_lower(20,2) AND drop_3h < -5% AND hora NOT in {16,17,18,19} AND vol_rel <= 5
  - Scoring: body severity + drop severity + RSI(7) oversold + volum + hora

**3. Paper Trading**
- `PaperExecutor` implementa mateixa interfície que `LiveExecutor`
- Quan obre: registra entry_price = open de la candle següent (poll BS per el preu)
- Quan tanca (1H després): registra exit_price = close de la candle
- Calcula P&L = nominal × (exit - entry) / entry - fee

**4. Risk Manager**
- State machine:
```
REAL → PAPER: si 2 pèrdues consecutives
PAPER → REAL: si 1 senyal en paper hauria guanyat
STOPPED: si capital < 100$ (requereix intervenció manual)
```
- Regles:
  - Max 1 posició simultània
  - Sizing: col = min(max(capital × 0.20, 15), 60), leverage = 100x
  - No SL (l'estratègia ho requereix — el rebot necessita espai)
  - Exit: close de la candle 1H (hold exactament 1 hora)

**5. Portfolio Tracker**
- SQLite amb taules: `trades`, `equity_snapshots`, `signals` (tots, incloent rebutjats)
- Trade: {id, timestamp, asset, strategy, direction, entry_price, exit_price, collateral, leverage, nominal, fee, pnl, pnl_pct, score, tier, mode(paper|real), paper_mode_reason}
- Equity snapshot cada hora: {timestamp, capital, unrealized_pnl, drawdown_pct}

**6. Execution Bridge**
```python
class IExecutor(Protocol):
    async def open_long(self, symbol: str, collateral: float, leverage: float) -> Position: ...
    async def close_position(self, position_id: str) -> TradeResult: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_balance(self) -> Balance: ...

class PaperExecutor:  # simula localment
class LiveExecutor:   # POST al BrokerageService via httpx
```

**7. FastAPI endpoints propis del TradingAgent**
- `GET /health` — health check
- `GET /status` — estat: mode (paper/live), capital, posició oberta, últim senyal, consec_losses
- `GET /trades` — historial trades (query SQLite)
- `GET /equity` — equity curve
- `POST /mode/paper` — forçar paper mode
- `POST /mode/live` — tornar a live
- `POST /stop` — stop total

#### Funcionalitats futures (dissenyar per, NO implementar)

**8. AI Agent Orchestrator** — Component amb Claude API que:
- Analitza estat del portfolio periòdicament
- Pot decidir pausar/reprendre estratègies
- Ajusta sizing basant-se en drawdown recent
- Genera reports setmanals

**9. Multi-strategy** — Múltiples IStrategy actives amb allocation engine:
- Capitulation Scalp 1H (crypto, 24/7)
- Portfolio D (NVDA dilluns, etc., D1, market hours)
- Capital repartit entre estratègies

**10. Web UI** — Dashboard amb equity curve, trades, senyals en temps real.

### Requisits tècnics

- **Python 3.11**, asyncio, tipat fort (dataclasses, Protocol, TypeAlias)
- **FastAPI** per API REST pròpia
- **Docker Compose** — 1 servei, mateixa Docker network que BrokerageService (`brokerage_net`)
- **httpx** async per comunicar amb BS
- **SQLite** per persistència (trades, equity, config)
- **Tests**: scripts Python purs (NO pytest). Format: `def _run_tests(): ... if __name__=="__main__": sys.exit(0 if ok else 1)`. Suite: `./test.sh <fitxer>`.
- **Logging** estructurat
- **Config**: env vars + YAML per estratègies
- Estil de codi: com BrokerageService (dataclasses, domain objects, foundation layer)

### Arquitectura interna suggerida

```
TradingAgent/
├── apps/
│   └── agent/              # FastAPI app principal
│       ├── app.py          # factory, lifespan, startup
│       └── routes.py       # /health, /status, /trades, /equity, /mode/*
├── packages/
│   ├── market/             # Market Monitor
│   │   ├── monitor.py      # poll BS, calcular indicadors
│   │   └── indicators.py   # BB, RSI, drop, vol_rel
│   ├── strategy/           # Strategy Engine
│   │   ├── base.py         # IStrategy protocol, Signal dataclass
│   │   └── capitulation_scalp.py  # implementació concreta
│   ├── risk/               # Risk Manager
│   │   ├── manager.py      # state machine paper/real/stopped
│   │   └── sizing.py       # calcul col, leverage
│   ├── execution/          # Execution Bridge
│   │   ├── base.py         # IExecutor protocol
│   │   ├── paper.py        # PaperExecutor
│   │   └── live.py         # LiveExecutor (crida BS via httpx)
│   ├── portfolio/          # Portfolio Tracker
│   │   ├── tracker.py      # registrar trades, equity
│   │   └── db.py           # SQLite schema + queries
│   └── shared/             # compartit
│       ├── config.py       # env vars + YAML loading
│       ├── models.py       # dataclasses (Signal, Position, Trade, Balance)
│       └── logging.py      # structured logging
├── strategies/             # YAML configs per estratègia
│   └── capitulation_scalp_1h.yaml
├── tests/
│   ├── test_indicators.py
│   ├── test_strategy.py
│   ├── test_risk_manager.py
│   └── test_paper_executor.py
├── docker/
│   └── Dockerfile
├── docker-compose.yml      # s'enganxa a brokerage_net
├── test.sh
├── scripts/
│   └── run_tests.sh
└── CLAUDE.md
```

### El que necessito de tu

1. **Revisa i millora** l'estructura de directoris proposada
2. **Diagrama de components** amb fluxos de dades entre ells
3. **Interfícies clau** amb codi Python real (Protocol/dataclass amb signatures completes)
4. **Flux de dades** detallat: timer → poll → indicadors → strategy → risk → execute → track
5. **Pla d'implementació** en fases (MVP → V1 → V2) amb què fer a cada fase
6. **Decisions d'arquitectura** raonades (asyncio patterns, error handling, retry, graceful shutdown)
7. **Schema SQLite** per les taules principals

Respon en català. Sigues concret — prefereixo codi Python esquemàtic real que no pas diagrames abstractes. El nivell de detall ha de permetre començar a implementar directament.

---

*Fi del prompt*
