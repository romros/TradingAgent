# Contracte estricte d'evidència d'Alquímia

Des de la cadena `schema_version=2`, un rebut no és vàlid només perquè apunta a
un fitxer amb el hash correcte. `stage_artifact_contract.py` interpreta el JSON
i comprova la seva identitat, el llinatge i els llindars congelats de
`methodology_v3.json`.

## Invariants

- Les vuit etapes s'executen en ordre i `REJECT`/`BLOCK` són terminals.
- Els candidats d'una etapa posterior només poden ser un subconjunt dels
  anteriors.
- El holdout no es pot consultar abans de superar robustesa i economia.
- Validació temporal, Monte Carlo, estrès de costos, economia de 200 USDC,
  traducció exacta i paritat tenen camps i llindars verificables.
- Cap cadena autoritza live.
- `synthetic_control` només prova el cablejat: encara que passi 8/8 etapes, mai
  no pot ser promocionable ni quedar `paper_ready`.
- Les cadenes v1 continuen sent llegibles per traçabilitat però retornen
  `LEGACY_CHAIN_WITHOUT_STRICT_STAGE_ARTIFACT_CONTRACT`; no constitueixen la
  nova prova semàntica.

## Control reproduïble

```bash
python3 -m lab.sq_bridge.e2e_control \
  --output-dir lab/sq_bridge/evidence/alquimia_v3_strict_control
```

El resultat esperat és `valid=true`, `operational_control_complete=true` i els
tres límits de seguretat a fals: `promotable`, `paper_ready` i
`live_authorized`.

Per executar tota la regressió amb les dependències de càlcul disponibles:

```bash
PYTHONPATH=.venv-alquimia/lib/python3.12/site-packages \
  python3 -m pytest -q lab/sq_bridge
```

Aquest control no és una simulació de mercat, no afirma rendiment i no pot ser
substituït pels artefactes observats d'una candidata StrategyQuant real.
