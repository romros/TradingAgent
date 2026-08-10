# EURUSD D1 — pont SQ, Dukascopy i Ostium per Alquímia v4

## Decisió

`PASS_D1_SOURCE_MAPPING`, exclusivament com a autorització de recerca. No
autoritza rendiment, SQCLI, paper ni live. El gate de costos executables de
200 USDC continua sent obligatori abans de formular o provar una hipòtesi.

No existeix solapament simultani entre el CSV SQ disponible, que acaba el gener
de 2026, i la captura Ostium, que comença el febrer. Per no confondre absència de
dades amb paritat, la certificació usa un pont de dues potes sobre una mateixa
font canònica:

1. SQ CSV ↔ API Dukascopy, del 20 al 29 de gener de 2026, a M1;
2. API Dukascopy ↔ API Ostium, del 19 de febrer al 8 d'agost de 2026, agregat a
   dies UTC complets.

No s'ha consultat cap retorn d'estratègia. L'agregació UTC D1 només certifica la
transferència de preus entre fonts; una futura hipòtesi haurà de congelar la
seva sessió de trading de manera independent.

## Resultat observat

| Pota | Mesura | Resultat | Gate |
|---|---|---:|---:|
| SQ ↔ Dukascopy | files SQ | 9.827 | ≥5.000 |
| SQ ↔ Dukascopy | cobertura SQ | 100% | ≥99% |
| SQ ↔ Dukascopy | OHLC coincident | 100% | ≥99% |
| SQ ↔ Dukascopy | màxima diferència OHLC | 0 | ≤1e-5 |
| Dukascopy ↔ Ostium | dies complets comuns | 122 | ≥60 |
| Dukascopy ↔ Ostium | cobertura de dies | 100% | ≥90% |
| Dukascopy ↔ Ostium | correlació retorn D1 | 0,999999604 | ≥0,99 |
| Dukascopy ↔ Ostium | direcció coincident | 100% | ≥95% |
| Dukascopy ↔ Ostium | diferència close p95 | 0 bps | ≤5 bps |

La ruta Dukascopy pagina amb `next_ts`, mentre que la ruta Ostium legacy pagina
amb `next_offset`. El lector accepta explícitament els dos contractes i falla si
un cursor es repeteix. Les memòries cau brutes són regenerables, no es
versionen, i s'escriuen amb gzip determinista; l'artefacte conserva files i
SHA-256 de cada captura.

## Reproducció

```bash
.venv/bin/python -m lab.sq_bridge.eurusd_d1_bridge_mapping_v4 \
  --sq-csv '/mnt/volume-SQ/user/t915_export/EURUSD_M1_dukas_M1_UTCMinus05-M1-No Session.csv' \
  --sq-from 2026-01-20T00:00:00 --sq-to 2026-01-29T00:00:00 \
  --mapping-from 2026-02-19T00:00:00 --mapping-to 2026-08-08T00:00:00 \
  --cache-dir data/alquimia_sources/eurusd_d1_bridge_v4 \
  --output lab/sq_bridge/evidence/eurusd_d1_bridge_mapping_v4.json
```

Implementació: `lab/sq_bridge/eurusd_d1_bridge_mapping_v4.py`. Evidència:
`lab/sq_bridge/evidence/eurusd_d1_bridge_mapping_v4.json`.

## Cobertura històrica

Una auditoria independent llegeix només timestamps dels 274 Parquet mensuals
Dukascopy. Reconstrueix la sessió Forex de 17:00 a 17:00 `America/New_York`,
inclòs el canvi DST, i considera completa una sessió amb almenys el 95% de
1.440 minuts. Els dies laborables inclouen festius al denominador, una decisió
conservadora.

- tram seleccionat sense mirar rendiment: **05/05/2003–27/02/2026**;
- 5.884 sessions completes de 5.955 esperades;
- cobertura global: **98,8077%**;
- pitjor segment anual: **91,9231%** (mínim 80%).

Decisió: `PASS_HISTORICAL_COVERAGE`. El rebut inclou el manifest i SHA-256 de
cada partició. Aquesta cobertura autoritza dissenyar train/validation/OOS i un
holdout segellat, però no afirma que un edge antic continuï vigent. La robustesa
temporal i els règims recents ho hauran de demostrar més endavant.

El CSV SQ emprat al pont acaba el gener de 2026: certifica identitat, no prova
que el recurs instal·lat a SQ contingui tot el tram. Abans d'una campanya caldrà
construir/importar un recurs SQ des d'aquestes particions i verificar-ne dates i
hash independentment.

Implementació: `lab/sq_bridge/eurusd_d1_historical_coverage_v4.py`. Evidència:
`lab/sq_bridge/evidence/eurusd_d1_historical_coverage_v4.json`.

## Següent gate

Esperar que `scripts/capture_ostium_research_universe_economics.sh` completi almenys
30 observacions, tres dies laborables i sis hores UTC per EURUSD. Només aleshores
es congelaran costos base, conservadors i d'estrès per a 200 USDC. Si aquests
costos passen, el següent pas és una única família D1 preregistrada i un screen
train-only v4; no una exploració retrospectiva de resultats antics.

Després de cada captura, `scripts/refresh_eurusd_v4_preflight.sh` recompòn dos
artefactes regenerables a `data/ostium_economics_universe/`: costos i preflight.
El cost es calcula captura per captura com fee open+close, spread i slippage
long+short; base usa mediana, conservador p95 i estrès el màxim de 2× mediana o
p95 més 0,10 USDC d'oracle no reemborsat. Amb cobertura immadura no conserva
cap valor provisional com a cost congelat. Un `PASS` del preflight només
autoritza `hypothesis_screen`; `sqcli_authorized` continua sent fals.
