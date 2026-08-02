# Benchmark difícil de retrieval

Corpus: 24 fonts; motor SQLite FTS5/BM25 amb stopwords i cobertura lexical mínima.
Dataset: 19 preguntes — 16 answerables, 3 que exigeixen abstenció.

## Resultat 2026-08-02

- Recall@5 answerable: **0,81**;
- MRR@5 answerable: **0,88**;
- no-answer accuracy: **1,00**;
- benchmark lexical original (23 preguntes): Recall@5 i MRR@5 **1,00**.

Les consultes noves sobre règim modern, costos d'Ostium i ordre dels mòduls SQ
recuperen la font correcta en primera posició. Encara es perden dues paràfrasis
antigues sense solapament suficient; és un límit real de cerca lexical.

## Decisió

No activar embeddings encara. Dinou preguntes difícils són insuficients per justificar
cost, dependència i reindexació. Ampliar a 50 preguntes cegues i comparar:

1. FTS5 actual;
2. FTS5 amb diccionari de sinònims de domini versionat;
3. embeddings només com a experiment efímer;
4. híbrid, si vectors milloren casos semàntics sense empitjorar abstenció/cites.

Gate provisional: millora mínima de 0,15 Recall@5 sobre les preguntes semàntiques,
no-answer accuracy >=0,90 i cites correctes. El llindar es congela abans de provar
embeddings; no és una afirmació que aquests siguin necessaris.
