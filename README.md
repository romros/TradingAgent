# TradingAgent

> **OBJECTIU NOU I ÚNIC (esmenat 2026-08-16):** recerca teòrica d'una cartera
> no-cripto amb actius del catàleg públic d'Interactive Brokers, escenaris de
> capital petit (màxim 3.000 USD) i compounding, que superi buy-and-hold net de costos o aporti
> una millora clara i mesurable de risc-retorn. La cartera actual de cinc
> edges és la baseline defensiva, no l'èxit final. L'objectiu
> anterior d'Ostium està tancat. Començar sempre per
> [CURRENT_OBJECTIVE.md](CURRENT_OBJECTIVE.md).

La cartera final està limitada a 6–8 estratègies traçables individualment;
mai s'afegeixen peces només per arribar al mínim.

TradingAgent és el cervell de senyal, context i risc. Una futura integració de
BrokerageService amb IBKR només es considerarà després d'un `THEORETICAL_PASS`.

La descoberta principal es fa amb **StrategyQuant/SQCLI**. Python valida els
finalistes, recalcula costos/marge/compounding d'IBKR i construeix la cartera;
no substitueix SQ com a motor inicial de cerca.

## Estat històric anterior — tancat, no reprendre

`capitulation_d1` s'executava només en paper sobre MSFT/NVDA/NDXUSD. La resta del
projecte continua en **fase de validació**: cap estratègia nova passa a paper o
live sense evidència temporal, economia de 200 USDC, paritat Ostium i gate de
producció. Veure [AGENTS_ARQUITECTURA.md §9](AGENTS_ARQUITECTURA.md).

### Estratègia històrica en paper: Capitulation D1

LONG d'un dia després d'una capitulació D1. MSFT és l'actiu primari; NVDA i
NDXUSD són complementaris. El paper probe té encara una mostra massa petita per
confirmar el backtest i l'estat live continua `LIVE_NOT_READY`.

La recerca Alquímia més recent ha rebutjat el momentum BTC/ETH/SOL v15–v17 en
validació temporal. Les fonts BTC/ETH/SOL són reproduïbles i ETH/SOL tenen
roundtrip SQ amb OHLC exacte, però encara no paritat executiva Ostium.

### Probe forward separat: MSFT close drift

`msft_close_drift_v24` disposa d'un motor paper close-to-close independent amb
200 USDC virtuals, 4x, risc de l'1%, cost roundtrip de 36 bps i holding de cinc
sessions. Usa `source=ostium_clean` i una SQLite diferent; no comparteix capital
ni operacions amb `capitulation_d1`. Actualment resta `WARMING_UP` fins acumular
102 sessions completes. Smoke manual read-only/paper:

```bash
MSFT_DRIFT_DB_PATH=data/msft_close_drift_probe.db \
python -c 'from packages.runtime.msft_close_drift_runner import run_msft_close_drift_probe; print(run_msft_close_drift_probe())'
```

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
