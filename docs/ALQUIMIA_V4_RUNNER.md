# Runner reprenable d'Alquímia v4

`lab/sq_bridge/v4_campaign_runner.py` converteix el contracte v4 en una cadena
operativa. No conté cap estratègia ni executa ordres de trading: orquestra
programes deterministes que produeixen els deu artefactes d'evidència.

## Garanties

- una sola etapa per `run-next`;
- ordres com arrays, sense shell ni interpolació de comandes;
- `market_preflight → hypothesis_screen → sq_generation` estricte;
- `REJECT/BLOCK` terminal: SQ no s'invoca després d'un screen fallit;
- manifest congelat per SHA-256 al primer run;
- lock contra dues execucions simultànies;
- timeout per etapa;
- stdout/stderr resumits per mida i SHA-256, amb cua limitada a 16 KiB i secrets
  convencionals ocults; es processen mitjançant fitxers temporals, de manera que
  una execució llarga no acumula tota la sortida a RAM ni la persisteix;
- artefacte `.pending`, validació completa i reemplaçament atòmic;
- una ordre o artefacte fallit deixa `chain.json` intacte i és reprenable;
- `sq_generation` pot reprendre el mateix run després d'una caiguda gràcies als
  rebuts durables de preflight i start, sense iniciar SQ una segona vegada;
- `latest.json` és una projecció per a monitoratge o una futura API;
- cap cadena pot autoritzar live.

L'esquema per a manifests és
[`alquimia-v4-runner.schema.json`](../academia/manifests/alquimia-v4-runner.schema.json).
Cada command pot usar `{artifact}`, `{stage}`, `{state_dir}` i `{manifest}`. El
programa de l'etapa ha d'escriure el seu JSON exactament a `{artifact}`.

## Operació

```bash
python -m lab.sq_bridge.v4_campaign_runner campaign.json status
python -m lab.sq_bridge.v4_campaign_runner campaign.json run-next
```

Després de cada invocació s'inspecciona `status`. L'operador o scheduler torna a
cridar `run-next` només quan vulgui avançar una etapa. Per això una reconstrucció
de SQCLI, un reinici de màquina o una llicència caducada no fan perdre les etapes
anteriors.

## Layout regenerable

```text
state_dir/
  runner_contract.json   # hash immutable del manifest
  chain.json             # font de veritat atòmica
  latest.json            # projecció de monitoratge
  artifacts/             # un JSON validat per etapa
  logs/                  # ordre, sortida, retorn i timeout
  sq-runs/               # preflight/start/watchdog/final d'SQ reprenables
  .runner.lock
```

Per canviar una ordre, timeout o qualsevol camp del manifest s'ha de crear una
campanya/state nou. Editar el manifest d'una campanya iniciada retorna
`MANIFEST_CHANGED` i no altera la cadena.

Els logs serveixen per diagnosticar i comprovar la identitat de la sortida, no
com a magatzem de resultats. Cada programa d'etapa ha de posar l'evidència útil
a l'artefacte JSON. La redacció és una defensa addicional, no substitueix evitar
imprimir credencials des del programa invocat.

## Comandament SQ v4

La fase `sq_generation` del manifest usa `sq_generation_stage_v4.py`. El rebut
d'importació s'ha d'haver creat prèviament sense iniciar SQ:

```json
{
  "command": [
    ".venv/bin/python", "-m", "lab.sq_bridge.sq_generation_stage_v4",
    "--import-receipt", "/state/import/sqcli_import_receipt.json",
    "--hypothesis", "d1_breakout",
    "--campaign-id", "eurusd-d1-breakout-v4",
    "--methodology", "lab/sq_bridge/methodology_v4.json",
    "--run-dir", "{state_dir}/sq-runs/d1_breakout",
    "--output", "{artifact}"
  ],
  "timeout_seconds": 7200,
  "cwd": "/mnt/volume-SQ/dev/TradingAgent"
}
```

El comandament valida batch→import→CFX reserialitzat, inicia o reprèn el run,
espera el log final i construeix l'artefacte observat. Zero SQX produeix un
`REJECT` terminal amb pressupost/log preservats; una fallada operacional deixa
la cadena intacta per reprendre.

## Límit actual

El runner prova l'orquestració i recuperació. Encara falta una campanya real v4
que produeixi una candidata SQ sobrevivint
fins a paper. US500+VIX no es pot manifestar fins que el collector d'Ostium
completi tres dies de costos executables.
