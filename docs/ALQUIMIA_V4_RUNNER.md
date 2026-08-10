# Runner reprenable d'Alquímia v4

`lab/sq_bridge/v4_campaign_runner.py` converteix el contracte v4 en una cadena
operativa. No conté cap estratègia ni executa ordres de trading: orquestra
programes deterministes que produeixen els nou artefactes d'evidència.

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
  .runner.lock
```

Per canviar una ordre, timeout o qualsevol camp del manifest s'ha de crear una
campanya/state nou. Editar el manifest d'una campanya iniciada retorna
`MANIFEST_CHANGED` i no altera la cadena.

Els logs serveixen per diagnosticar i comprovar la identitat de la sortida, no
com a magatzem de resultats. Cada programa d'etapa ha de posar l'evidència útil
a l'artefacte JSON. La redacció és una defensa addicional, no substitueix evitar
imprimir credencials des del programa invocat.

## Límit actual

El runner prova l'orquestració i recuperació. Encara falta una campanya real v4
que proporcioni els commands concrets i produeixi una candidata SQ sobrevivint
fins a paper. US500+VIX no es pot manifestar fins que el collector d'Ostium
completi tres dies de costos executables.
