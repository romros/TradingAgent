# TradingAgent

Bot de trading automatitzat que consumeix [BrokerageService](../BrokerageService) per operar a Ostium (DEX crypto perpetual futures).

## Estat: LAB — validació estratègica

El projecte està en **fase de validació**. La construcció del bot productiu (BUILD) està condicionada a disposar d'una estratègia amb expectativa de rendibilitat suficient. Veure [AGENTS_ARQUITECTURA.md §9](AGENTS_ARQUITECTURA.md) per al gate de producció.

### Estratègia candidate: Capitulation Scalp 1H

LONG crypto (ETH, BTC, SOL) després d'un crash extrem en 1H. Validada amb Monte Carlo (3/3 PASS) i Walk-Forward (7/9 anys positius). Edge estadísticament significatiu (+15-35pp vs random entry).

**Amb liquidació simulada (T1)**: leverage 20x, EV +5.6$/trade, 250$→1.114$ en 8.6 anys (x4.5). Resultats modestos — cas econòmic en revisió.

## Arquitectura

```
TradingAgent (cervell)  ──HTTP──>  BrokerageService (cos)
  decideix QUÈ i QUAN                executa, dades, posicions
```

- **TF operatiu**: 1H
- **Modes**: PAPER / LIVE / STOPPED
- **Leverage**: 20x (recalibrat amb liquidació simulada, era 100x)

## Docs

- [AGENTS_ARQUITECTURA.md](AGENTS_ARQUITECTURA.md) — disseny, components, fluxos, gate de producció
- [docs/ESTAT.md](docs/ESTAT.md) — estat operatiu, evidència, decisions
- [CLAUDE.md](CLAUDE.md) — regles pel coding assistant

## Lab

```bash
# Monte Carlo + Walk-Forward
python3 lab/studies/mc_walkforward_capitulation.py --cache /tmp/crypto_1h_cache.pkl

# Stress test + leverage recalibration (T1)
python3 lab/studies/leverage_recalibration.py --cache /tmp/crypto_1h_cache.pkl
```

## Dependències

- Python 3.11, FastAPI, httpx, asyncio
- BrokerageService (gateway :8081) a la mateixa Docker network
