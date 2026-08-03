# TradingAgent

Bot de trading automatitzat que consumeix [BrokerageService](../BrokerageService) per operar a Ostium (DEX crypto perpetual futures).

## Estat: LAB + paper probe controlat

`capitulation_d1` s'executa només en paper sobre MSFT/NVDA/NDXUSD. La resta del
projecte continua en **fase de validació**: cap estratègia nova passa a paper o
live sense evidència temporal, economia de 200 USDC, paritat Ostium i gate de
producció. Veure [AGENTS_ARQUITECTURA.md §9](AGENTS_ARQUITECTURA.md).

### Estratègia activa en paper: Capitulation D1

LONG d'un dia després d'una capitulació D1. MSFT és l'actiu primari; NVDA i
NDXUSD són complementaris. El paper probe té encara una mostra massa petita per
confirmar el backtest i l'estat live continua `LIVE_NOT_READY`.

La recerca Alquímia més recent ha rebutjat el momentum BTC/ETH/SOL v15–v17 en
validació temporal. Les fonts BTC/ETH/SOL són reproduïbles i ETH/SOL tenen
roundtrip SQ amb OHLC exacte, però encara no paritat executiva Ostium.

## Arquitectura

```
TradingAgent (cervell)  ──HTTP──>  BrokerageService (cos)
  decideix QUÈ i QUAN                executa, dades, posicions
```

- **TF operatiu paper**: D1
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
