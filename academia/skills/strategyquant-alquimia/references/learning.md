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

## Mapa de decisions après

| Evidència observada | Codi | No fer | Fer després |
|---|---|---|---|
| temporal passa, costos fallen | `TEMPORAL_PASS_COST_FAIL` | optimitzar o apalancar | canviar edge/fricció |
| desenvolupament passa, validació falla | `TEMPORAL_FAIL` | rescatar la família | hipòtesi nova i OOS nou |
| PF atractiu amb OOS minúscul | `LOW_SAMPLE_OR_VALIDATION_FAIL` | inferir edge del PF | més observacions sense canviar regles |
| total positiu, OOS per règim negatiu | `OOS_REGIME_FAIL` | ajustar sobre l'OOS vist | règim ex ante i OOS nou |

Si una consulta s'assembla a un cas, recuperar la fitxa d'observació abans de
recomanar. No extrapolar les magnituds d'una família a una altra.
