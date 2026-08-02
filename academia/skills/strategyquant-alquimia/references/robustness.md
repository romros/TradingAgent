# Robustesa orientada a decisions

Procediment complet: `academia/courses/strategyquant/02-RETESTER-CROSSCHECKS.md`.

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

No comptar files `futurePeriod` com a validació. Són la recepta futura suggerida pel
procés, no trades futurs observats.

## Monte Carlo

Distingir manipulació de trades (ràpida) de retest amb dades, paràmetres o costos
(car). Cada prova respon una pregunta; no sumar passes com evidència independent.
Si el paquet només conté configuració Monte Carlo però cap resultat, marcar-lo
`operational`, no `tested`.

Fixar els gates abans de veure el pass rate. Mai abaixar-los perquè sobreviuen
pocs candidats ni apujar-los perquè en sobreviuen molts; això converteix el gate
en una altra capa d'optimització. Zero supervivents és un resultat vàlid.

Abans d'executar, enumerar els crosschecks actius i exigir coincidència exacta
amb el pla; els projectes poden heretar proves. Comparar també els llindars de
la metodologia amb les condicions d'acceptació del `.cfx`. Registrar per separat
simulacions sol·licitades, executades i membres del paquet: el resultat base pot
ser un membre addicional.

No resumir costos com «2x». Enumerar spread, slippage, comissió, swap/rollover i
impacte amb valors base i estressats. Si només varia un component, limitar la
conclusió a aquell component.

Aplicar temporalitat i economia del compte abans de MC car. Més leverage no crea
edge quan el risc o la mida mínima ja limiten el nocional.

## OOS

OOS usat per ajustar deixa de ser cec. Reservar holdout final. Si es mira, registrar
el peek i reclassificar-lo com a desenvolupament.
