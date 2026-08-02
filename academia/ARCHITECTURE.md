# Arquitectura

## Principis

- nucli genèric; coneixement específic en paquets de domini;
- fitxers JSON versionats com a font de veritat i SQLite com a projecció regenerable;
- recuperació lexical i metadades abans de components probabilístics;
- tota resposta recuperada conserva `source_id` i `locator`;
- media temporal fora del repositori; només metadades i notes transformadores;
- cap connexió amb execució de trading.

## Components

```text
source manifests ──validate/ingest──> SQLite + FTS5 ──search──> cites
       │                                      │
domain package manifests                 benchmark JSONL
       │                                      │
StrategyQuant (primer)                  Recall@k / MRR / latència
```

`tools/academia.py` és el port de referència sense dependències. Una futura API o
web ha de cridar aquesta capa o una interfície equivalent; no pot convertir la
base SQLite generada en font canònica.

## Límits de confiança

La ingesta valida forma i vocabularis, no veracitat. `source_level` qualifica la
font; `evidence_status` qualifica el fragment. Una cerca ordena coincidència
lexical, no confiança epistemològica. La promoció de claims continua requerint la
política i experiments reproduïbles.

## Evolució

1. ampliar fonts i benchmark amb judicis humans;
2. afegir filtres/CLI si els casos reals ho exigeixen;
3. encapsular la CLI en HTTP només quan existeixi un consumidor;
4. provar embeddings fora del camí principal només després del gate ADR-001;
5. adoptar una alternativa únicament si guanya el benchmark i manté cites.
