# Gate d'economia d'execució multi-mercat

## Per què existeix

Una sola captura d'SDK pot confirmar que un token existeix i descobrir la forma
dels camps, però no prova els costos típics. Spread, slippage i rollover canvien
amb l'hora i el règim. Alquímia exigeix 30 mostres de mercat obert, tres dies UTC
i sis hores UTC diferents abans de declarar preparat un model de costos
multidia o qualsevol gate de paper.

El collector és estrictament read-only. Consulta `getPairs()` i
`getSimSlippage()`; no signa, no envia ordres i no té credencials de trading.

## Univers monitoritzat

- `USD/JPY`, `GBP/USD`, `EUR/USD` i `XAU/USD`: cada dues hores.
- `US500/USD`: conserva el collector dedicat cada dues hores i no es duplica.

Les dades regenerables viuen fora de Git a `data/ostium_economics_universe/`.
Cada parell manté raw, normalitzat i resum. El resum inclou fee, spread,
slippage per nocional, cost roundtrip calculat captura per captura, rollover
separat long/short, leverage i mínim nocional.

## Primer smoke observat

El 2026-08-10 els cinc tokens van respondre amb mercat obert. Els fees observats
van ser 2 bps per USDJPY, GBPUSD, EURUSD i XAUUSD, i 1 bp per US500. Els antics
3 bps de GBPUSD/EURUSD/XAUUSD queden marcats com a potencialment obsolets, però
una sola mostra no els substitueix encara en backtests canònics.

Els rollovers tenen signe i magnitud diferents per costat. No es pot aplicar un
percentatge anual únic a long i short. El signe s'ha de validar contra la
convenció de càrrec/rebate del contracte abans de calcular PnL.

## Operació

```bash
scripts/capture_ostium_research_universe_economics.sh
scripts/install_ostium_research_universe_capture_cron.sh
```

Per EURUSD, el mateix job executa després
`scripts/refresh_eurusd_v4_preflight.sh`. El freezer exigeix novament 30/3/6,
identitat `pair_id=2 EUR/USD` i nocional 200; si falta qualsevol condició retorna
`BLOCK_INSUFFICIENT_EXECUTION_COVERAGE` sense promocionar mediana o p95. Quan
maduri construeix base/conservador/estrès, conserva l'oracle reemborsable separat i
recompon el preflight v4 amb hashes dels tres inputs.

`ostium_execution_universe_gate.py` combina els resums sense promocionar una
mostra provisional. Fins al `PASS`, una observació serveix per diagnosticar i
dissenyar escenaris conservadors, però estratègies multidia i paper queden
bloquejats. Cap resultat autoritza live.
