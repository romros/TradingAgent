# Robustesa orientada a decisions

| Pregunta | Prova útil | Senyal de risc |
|---|---|---|
| Depèn de l'ordre dels trades? | Monte Carlo trades | drawdown o pocs trades dominen |
| Depèn d'un valor exacte? | canvis de paràmetres | pic estret |
| Depèn de costos ideals? | costos adversos | l'edge desapareix |
| Depèn de reoptimització? | WFO/WFM petita | una cel·la funciona |
| Depèn del mercat/període? | retest addicional | només funciona al segment triat |
| És artefacte de precisió? | retest precís | canvien entrades o mètriques |

## WFM

Començar 3×3. Buscar regió connectada, trades per run, benefici repartit i drawdown
assumible. Si falla clarament, no ampliar per pescar una cel·la. Els llindars dels
exemples oficials són heurístiques, no lleis.

## Monte Carlo

Distingir manipulació de trades (ràpida) de retest amb dades, paràmetres o costos
(car). Cada prova respon una pregunta; no sumar passes com evidència independent.

## OOS

OOS usat per ajustar deixa de ser cec. Reservar holdout final. Si es mira, registrar
el peek i reclassificar-lo com a desenvolupament.
