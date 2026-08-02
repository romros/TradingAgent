# Benchmark difícil de retrieval

Corpus: 32 fonts; motor SQLite FTS5/BM25 amb stopwords i cobertura lexical mínima.
Dataset: 22 preguntes — 19 answerables, 3 que exigeixen abstenció.

## Resultat 2026-08-02

- Recall@5 answerable: **0,84**;
- MRR@5 answerable: **0,89**;
- no-answer accuracy: **1,00**;
- benchmark lexical original (23 preguntes): Recall@5 i MRR@5 **1,00**.

El dataset inclou ara règims, costos d'Ostium, ordre dels mòduls, Portfolio,
exportació i custom analysis. Es mantenen les dues paràfrasis antigues difícils.

## Decisió

No activar embeddings encara. Vint-i-dues preguntes difícils són insuficients per justificar
cost, dependència i reindexació. Ampliar a 50 preguntes cegues i comparar:

1. FTS5 actual;
2. FTS5 amb diccionari de sinònims de domini versionat;
3. embeddings només com a experiment efímer;
4. híbrid, si vectors milloren casos semàntics sense empitjorar abstenció/cites.

Gate provisional: millora mínima de 0,15 Recall@5 sobre les preguntes semàntiques,
no-answer accuracy >=0,90 i cites correctes. El llindar es congela abans de provar
embeddings; no és una afirmació que aquests siguin necessaris.
