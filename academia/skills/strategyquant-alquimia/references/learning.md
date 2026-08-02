# Aprendre de campanyes

Llegir artifacts en mode només lectura. No reescriure resultats ni accedir a
credencials. Conservar path, SHA-256, mètriques observades i decisió.

## Cicle

1. Normalitzar gates en una observació.
2. Separar observació (`PF`, trades, costos) d'inferència (“edge insuficient”).
3. Assignar un codi de fracàs o continuació.
4. Afegir fracassos a `academia/experiments/failure-memory.json` amb què no repetir.
5. Proposar una nova direcció, no un ajust que reutilitzi el holdout.
6. Promocionar un insight a `tested`; reservar `verified` per reproduccions.

## Codis inicials

- `TEMPORAL_FAIL`: no supera la seqüència temporal.
- `TEMPORAL_PASS_COST_FAIL`: patró temporal no capturable després de costos.
- `LOW_SAMPLE_OR_VALIDATION_FAIL`: resultat atractiu sense mostra OOS suficient.
- `OOS_REGIME_FAIL`: rendiment total amaga degradació en anys posteriors.
- `TEMPORAL_AND_COST_PASS`: candidat apte per al següent gate, no per live.

No crear un codi nou si un d'existent explica l'acció següent.
