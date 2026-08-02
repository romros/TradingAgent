# Acadèmia basada en evidències

Base de coneixement genèrica i ampliable per aprendre, ensenyar i consultar amb
evidències. StrategyQuant és el primer paquet de domini. No és un arxiu de
promeses de rendibilitat ni participa en l'execució de trading.

## Objectius

- respondre preguntes de SQ amb font, versió i nivell de confiança;
- convertir manuals i vídeos en coneixement verificat amb timestamps;
- provar localment les configuracions sobre SQX 143.2708;
- produir cursos, guions i demostracions pròpies;
- reutilitzar el corpus en una futura web i un servidor MCP;
- mantenir separats coneixement tècnic, evidència quantitativa i opinió.

## Estructura

```text
academia/
├── README.md
├── POLICY.md                 # evidència, copyright i promoció de coneixement
├── sources/                  # fitxes de manuals, webs, papers i vídeos
├── notes/                    # destil·lacions amb cites i contradiccions
├── courses/                  # cursos i lliçons pròpies
├── experiments/              # proves reproduïbles sobre la nostra versió SQ
├── media/                    # manifests; no vídeos de tercers versionats
├── manifests/                # contractes de manifest
├── packages/                 # extensions de domini (StrategyQuant primer)
├── benchmark/                # consultes i judicis de rellevància
├── audits/                   # decisions sobre eines i dependències
├── deploy/                   # contracte de desplegament futur
├── catalog/                  # esquema SQLite/FTS i decisions de recuperació
└── tools/                    # ingesta, validació i cerca deterministes
```

## Ús local

```bash
python3 academia/tools/academia.py --db /tmp/academia.db ingest academia/sources/strategyquant/*.json
python3 academia/tools/academia.py --db /tmp/academia.db ingest-claims academia/claims/strategyquant/*.json
python3 academia/tools/academia.py --db /tmp/academia.db search "filtre correlació" --domain strategyquant
python3 academia/tools/academia.py --db /tmp/academia.db benchmark academia/benchmark/queries.jsonl
python3 -m unittest discover -s academia/tests -v
python3 academia/tools/experiment_gate.py academia/experiments/examples/wfm-region-synthetic.json
python3 academia/tools/strategy_review.py academia/experiments/examples/three-candidates.json
python3 academia/tools/reality_transfer.py academia/experiments/examples/reality-transfer-xau-example.json
```

Per entendre SQ en ordre i sense perdre l'objectiu global, començar per
`courses/strategyquant/SQ-END-TO-END-MAP.md`; per convertir resultats històrics en
una decisió actual, continuar amb `courses/strategyquant/NUMBERS-TO-REALITY.md`.

La base `.db` és regenerable i ignorada per Git. El curs preexistent fora d'aquest
directori no es migra ni es modifica dins d'aquest canvi.

## Flux d'una font

```text
DESCOBERTA → CAPTURA → DESTIL·LACIÓ → CONTRAST → EXPERIMENT → VERIFICADA/REBUTJADA
```

Cap afirmació d'un vídeo es marca `verified` només perquè el presentador sembli
expert. Cal contrast documental o una prova local reproduïble.

## Recuperació

Primera etapa: SQLite + FTS5/BM25, filtres per versió, tipus de font, tema i estat
d'evidència. És auditable i no necessita tokens.

Embeddings/RAG només es promocionaran si un benchmark de preguntes SQ demostra que
recuperen millor que FTS5. Si s'afegeixen, seran híbrids: filtre estructurat + BM25 +
vectors + reranking, sempre retornant fragments i fonts, mai una resposta sense cita.
