Sempre en català
Llegeix AGENTS_ARQUITECTURA.md abans de fer tasques
Llegeix docs/ESTAT.md per saber per on anem
Revisa el codi ja fet per veure com es fan les coses
Pregunta abans d'inventar

# Projecte TradingAgent

Bot de trading automatitzat que consumeix BrokerageService per operar a Ostium.
TradingAgent = cervell (decideix QUÈ i QUAN). BrokerageService = cos (executa, dades).

## Principis

- imports sempre a capçalera
- zero hardcode (tot configurable via env/YAML)
- rutes FastAPI primes — lògica als paquets
- tests com scripts Python purs (NO pytest)
- cap feature es dona per tancada sense test
- opt-in per tests amb xarxa (network smokes)
- lab/ és per explorar; packages/ ha de sortir net
- float (no Decimal) per MVP
- UTC always

## Stack

- Python 3.11, FastAPI, asyncio, httpx
- SQLite per persistència
- Docker Compose (mateixa network que BrokerageService)
- Tests: `./test.sh <fitxer>`, suites: `./scripts/run_tests.sh`

## Arquitectura

- `apps/agent/` — FastAPI app (rutes primes)
- `packages/runtime/` — engine, scheduler, shutdown
- `packages/brokerage/` — client HTTP cap al BS (:8081)
- `packages/market/` — monitor candles + indicadors
- `packages/strategy/` — IStrategy + implementacions
- `packages/risk/` — state machine paper/real/stopped + sizing
- `packages/execution/` — IExecutor + PaperExecutor + LiveExecutor
- `packages/portfolio/` — tracker + SQLite
- `packages/shared/` — models, config, logging

## BrokerageService API (gateway :8081)

- Candles: `GET /realtime/ohlcv/{symbol}?tf=1h&limit=200`
- Open: `POST /trade/api/v1/broker/orders/open` (202 async)
- Close: `POST /trade/api/v1/broker/orders/close`
- Positions: `GET /trade/api/v1/broker/positions?venue=ostium`
- Balance: `GET /trade/api/v1/broker/balance?venue=ostium`
- Operations: `GET /trade/api/v1/broker/operations/{id}`

## Commits

Sempre amb `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`
