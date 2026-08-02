# ADR-001 — Recuperació: FTS5 abans de vector RAG

Estat: acceptada provisionalment, 2026-08-02.

## Decisió

Començar amb SQLite FTS5/BM25 i metadades estructurades. No incorporar encara una
base vectorial ni un servei d'embeddings.

## Raons

- corpus inicial petit i terminologia precisa (`WalkForwardMatrix`, `RExpectancy`,
  noms XML, versions i errors);
- cerca lexical determinista, barata i explicable;
- filtres exactes per versió, autoritat i estat d'evidència;
- evita dependència de model, cost, privacitat i reindexacions prematures.

## Benchmark abans d'afegir embeddings

Crear almenys 50 preguntes representatives amb documents rellevants esperats.
Comparar Recall@5, MRR@10, precisió de cites, latència i cost entre:

1. FTS5/BM25;
2. embeddings;
3. híbrid BM25 + embeddings + reranking.

Només adoptar RAG vectorial si millora materialment el benchmark, especialment en
preguntes semàntiques, sense reduir la traçabilitat. Cache RAG serà una optimització
posterior per consultes repetides, mai la font de veritat.

