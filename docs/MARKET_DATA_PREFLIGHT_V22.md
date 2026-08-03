# Preflight de mercat Alquímia v22

Data de l'auditoria: 2026-08-03. Aquesta fase no calcula cap senyal ni PnL.
El seu objectiu és impedir que una campanya nova confongui disponibilitat de
fitxers amb paritat executable a Ostium.

## Política

`market_data_preflight.py` combina tres evidències independents:

1. coverage index Dukascopy amb mesos `done` i files reals;
2. registres de compatibilitat Ostium↔proxy;
3. persistència Parquet nativa d'Ostium.

Si dos registres discrepen, guanya l'observació amb `asof_ts` més recent. Una
absència o una observació actual que no tingui `allowed_for_backtest=true`
bloqueja la campanya. Un PASS només autoritza recerca proxy; mai paper o live.

## Resultat observat

| Mercat | Dukascopy | Ostium local | Paritat més recent | Decisió |
|---|---:|---:|---|---|
| EURUSD | 274 mesos, 10.050.611 M1 | 1 Parquet, 37.738 B | PARTIAL, corr 0,966, 71 min | `BLOCK_CURRENT_PARITY` |
| XAUUSD | 274 mesos, 7.799.353 M1 | cap Parquet al path canònic | PARTIAL, corr 0,960, 71 min | `BLOCK_CURRENT_PARITY` |
| MSFT | absent | 1 Parquet, 2.730 B | absent | `BLOCK_HISTORICAL_SOURCE` |
| NVDA | absent | 1 Parquet, 2.445 B | absent | `BLOCK_HISTORICAL_SOURCE` |
| NDXUSD | absent | 1 Parquet, 2.405 B | absent | `BLOCK_HISTORICAL_SOURCE` |

EURUSD i XAUUSD tenen registres anteriors més favorables, però entren en
conflicte amb el registre posterior de realtime. El preflight no tria el
resultat més convenient: aplica fail-closed i utilitza el més recent.

## Condicions de desbloqueig

Per EURUSD/XAUUSD, BrokerageService ha de produir una nova observació canònica
posterior, amb finestra representativa, `allowed_for_backtest=true` i un únic
registre autoritatiu o una regla de consolidació explícita. Després es torna a
executar el preflight; no s'edita l'artifact manualment.

Per MSFT/NVDA/NDXUSD cal una font històrica amb manifest, coverage, timestamps,
OHLC i política d'ajustos corporatius o, alternativament, acumular prou història
Ostium nativa. Els minuts actuals només demostren persistència tècnica, no
validesa per discovery D1. El proveïdor Dukascopy de BS no té mapping històric
per aquests símbols en l'estat inspeccionat.

## Reproducció

```bash
python3 -m lab.sq_bridge.market_data_preflight \
  --bs-root /mnt/volume-SQ/dev/BrokerageService \
  --symbols EURUSD XAUUSD MSFT NVDA NDXUSD \
  --registry /mnt/volume-SQ/dev/BrokerageService/datafiles/compat_reports/ostium_compat_registry.json \
  --registry /mnt/volume-SQ/dev/BrokerageService/datafiles/realtime_datalayer/compat_reports/ostium_compat_registry.json \
  --output lab/sq_bridge/evidence/market_data_preflight_v22.json
```

No es preregistra cap estratègia v22 fins que almenys un mercat retorni
`PASS_RESEARCH_PROXY_ONLY`. Això conserva el focus i evita gastar SQCLI o
evidència temporal sobre una cadena de dades que no es pot traslladar a Ostium.
