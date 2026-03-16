# TradingAgent

Bot de trading automatitzat que consumeix [BrokerageService](../BrokerageService) per operar a Ostium (DEX crypto perpetual futures).

## Arquitectura

```
TradingAgent (cervell)  ──HTTP──>  BrokerageService (cos)
  decideix QUÈ i QUAN                executa, dades, posicions
```

- **TF operatiu**: 1H
- **Assets**: ETH, BTC, SOL
- **Modes**: PAPER / LIVE / STOPPED
- **Estratègia MVP**: Capitulation Scalp 1H (LONG after crash extrem)

## Estructura

```
apps/agent/          FastAPI app (health, status, trades, mode)
packages/runtime/    Engine (2 loops: poll + close)
packages/brokerage/  Client HTTP cap al BS
packages/market/     Monitor candles + indicadors
packages/strategy/   IStrategy + implementacions
packages/risk/       State machine paper/real/stopped + sizing
packages/execution/  IExecutor + Paper + Live
packages/portfolio/  Tracker + SQLite
packages/shared/     Models, config, logging
strategies/          YAML configs per estratègia
lab/                 Exploració, backtest, MC, walk-forward
```

## Docs

- [AGENTS_ARQUITECTURA.md](AGENTS_ARQUITECTURA.md) — disseny, components, fluxos, SQLite schema
- [docs/ESTAT.md](docs/ESTAT.md) — estat operatiu, evidència
- [CLAUDE.md](CLAUDE.md) — regles pel coding assistant

## Desenvolupament

```bash
# Tests
./test.sh testing/unit/test_indicators.py
./scripts/run_tests.sh

# Docker
docker compose up -d trading-agent
```

## Dependències

- Python 3.11, FastAPI, httpx, asyncio
- BrokerageService (gateway :8081) a la mateixa Docker network
