# Benchmark difícil de retrieval

Corpus: 48 fonts; motor SQLite FTS5/BM25 amb stopwords i cobertura lexical mínima.
Dataset: 34 preguntes — 31 answerables, 3 que exigeixen abstenció.

## Resultat 2026-08-02

- Recall@5 answerable: **0,90**;
- MRR@5 answerable: **0,90**;
- no-answer accuracy: **1,00**;
- cinc consultes de deriva de contracte: Recall@5 **1,00** i MRR@5 **0,90**;
- la consulta nova sobre recursos inactius de l'Improver recupera l'evidència local a rang **1**;
- cinc consultes de notes de vídeo: Recall@5 i MRR@5 **1,00**;
- benchmark lexical original (27 preguntes): Recall@5 **1,00** i MRR@5 **0,98**.

El dataset inclou ara règims, costos d'Ostium, ordre dels mòduls, Portfolio,
exportació i custom analysis. Es mantenen les dues paràfrasis antigues difícils.

## Decisió

No activar embeddings encara. Trenta-quatre preguntes difícils són insuficients per justificar
cost, dependència i reindexació. Ampliar a 50 preguntes cegues i comparar:

1. FTS5 actual;
2. FTS5 amb diccionari de sinònims de domini versionat;
3. embeddings només com a experiment efímer;
4. híbrid, si vectors milloren casos semàntics sense empitjorar abstenció/cites.

Gate provisional: millora mínima de 0,15 Recall@5 sobre les preguntes semàntiques,
no-answer accuracy >=0,90 i cites correctes. El llindar es congela abans de provar
embeddings; no és una afirmació que aquests siguin necessaris.
