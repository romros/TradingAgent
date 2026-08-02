# Benchmark de recuperació

`queries.jsonl` és un conjunt llavor versionat de deu preguntes. Cada línia conté una pregunta,
el domini i els identificadors de font rellevants jutjats manualment. No és encara
el gate de 50 preguntes de l'ADR-001; serveix per detectar regressions del motor.

Execució reproduïble:

```bash
tmpdb=$(mktemp --suffix=.db)
python3 academia/tools/academia.py --db "$tmpdb" ingest academia/sources/strategyquant/*.json
python3 academia/tools/academia.py --db "$tmpdb" benchmark academia/benchmark/queries.jsonl
rm "$tmpdb"
```

Abans d'avaluar embeddings cal ampliar el conjunt a 50 preguntes, congelar els
judicis de rellevància i comparar exactament el mateix corpus. La latència s'ha de
mesurar al mateix host; els resultats generats no es versionen.
