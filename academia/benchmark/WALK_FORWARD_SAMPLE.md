# Resultat de la mostra Walk-Forward

Corpus de la mostra: tres documents oficials sobre WFO, WFM i valors avançats,
amb notes transformadores. Execució: SQLite FTS5/BM25, `limit=5`.

## Resultat esperat i reproducció

El conjunt global conté 15 preguntes; 9 cobreixen directament Walk-Forward. El
resultat es regenera, no es versiona com a JSON perquè la latència depèn del host:

```bash
db=$(mktemp --suffix=.db)
python3 academia/tools/academia.py --db "$db" ingest academia/sources/strategyquant/*.json
python3 academia/tools/academia.py --db "$db" benchmark academia/benchmark/queries.jsonl
rm "$db"
```

Gate de la mostra: `Recall@5 = 1.0`, `MRR@5 = 1.0` i les nou preguntes
Walk-Forward amb la primera font rellevant al rang 1.

## Lectura crítica

Aquest resultat verifica el cablejat i la separació entre documents, no la qualitat
d'un sistema complet. Les preguntes són poques, escrites després de conèixer el
corpus i lexicalment properes a les notes; per tant, el benchmark és fàcil i pot
sobreestimar retrieval real. Abans de comparar embeddings calen preguntes cegues,
paràfrasis, consultes sense coincidència lexical i judicis de rellevància externs.

## Mostra de resposta recuperable

Pregunta: «Què és preferible, una cel·la màxima aïllada o una regió estable?»

Resposta pedagògica: la documentació orienta a inspeccionar grups de combinacions
veïnes amb comportament consistent. Un màxim aïllat és més sensible a la selecció.
Això no demostra rendibilitat futura; només prioritza què investigar després.

Evidència: `sq_official_walk_forward_matrix_20150506#section:interpretation`.
