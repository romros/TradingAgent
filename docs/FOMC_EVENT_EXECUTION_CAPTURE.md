# Captura d’execució XAU/USD durant el FOMC

## Decisió i límit

La família `XAUUSD_FOMC_REACTION_V29` continua **rebutjada**: a 30 bps, cap dels
16 punts preregistrats passa desenvolupament. Aquesta captura no reobre v29 i no
consulta validació, OOS ni holdout. Genera evidència d’execució per decidir si té
sentit preregistrar una campanya futura i independent.

La pròxima decisió regular del calendari oficial de la Reserva Federal, congelat
el 10 d’agost de 2026, és el **16 de setembre de 2026**. La publicació s’assumeix
a les 14:00 `America/New_York`, d’acord amb l’horari oficial documentat per v29.

## Què captura

El procés consulta l’SDK oficial d’Ostium en mode `read-only`, només per al pair
5 `XAU/USD`, una vegada per minut entre 13:45 i 16:45 de Nova York:

| Fase | Finestra NY | Mínim de minuts oberts |
|---|---:|---:|
| pre | 13:45–13:59 | 10 |
| reaction | 14:00–14:30 | 20 |
| post | 14:31–16:45 | 60 |

Per cada captura desa quote bid/ask, spread, fees, límits i slippage simulat per
nocionals de 200, 400, 500 i 600 USDC. Rebutja identitat o data equivocades i
minuts duplicats. Les mostres de mercat tancat no compten.

El cost roundtrip neutral és un **proxy**, no fills observats:

`open fee + close fee + spread + slippage long simulat + slippage short simulat`

També calcula proxies long i short amb dues vegades el slippage del mateix costat.
El resum mostra p50, p95 i màxim per fase i nocional, amb hashes dels inputs.

## Operació fail-closed

Instal·lació idempotent del pròxim esdeveniment:

```bash
scripts/install_ostium_fomc_event_capture_cron.sh
```

El cron s’activa pel dia i mes, però el wrapper comprova també l’any, la data
exacta i la finestra NY **abans** de tocar Docker o la xarxa. `flock` evita
solapaments. Fora de finestra finalitza amb `OUTSIDE_FOMC_*` i no captura res.
Les dades persistents, ignorades per Git, queden a:

`data/ostium_event_economics/fomc_2026-09-16/`

Execució manual equivalent, només durant la finestra correcta:

```bash
FOMC_EVENT_DATE=2026-09-16 scripts/capture_ostium_fomc_event_economics.sh
```

## Interpretació posterior

`EVENT_EXECUTION_EVIDENCE_READY` només significa que les tres fases tenen prou
observacions. No prova rendibilitat, no autoritza paper/live i no converteix el
slippage simulat en fills reals. Si passa, el següent pas admissible és congelar
una campanya nova amb costos derivats de p95 i mantenir intactes els períodes
2019–2026 que v29 no va obrir.
