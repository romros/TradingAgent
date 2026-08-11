# Construcció de cartera Alquímia v4

## Objectiu

La validació individual no és suficient: dues estratègies poden superar tots
els gates i representar pràcticament la mateixa exposició. La porta de cartera
selecciona entre quatre i vuit estratègies abans d'obrir el holdout final.

El contracte queda preregistrat a `methodology_v4.json`:

- mínim 4 i màxim 8 estratègies;
- màxim 12 candidates individuals d'entrada;
- una candidata per hipòtesi dirigida;
- correlació absoluta màxima de PnL diari net d'estrès: 0,70;
- Jaccard màxim de dates de sortida: 0,80;
- almenys 30 dates de sortida a la unió de cada parella;
- màxim dues posicions simultànies;
- risc de stop simultani màxim del 3% del compte;
- capital simultani compromès màxim del 60%, preservant un 40% de reserva;
- màxima cardinalitat i, després, expectativa, profit factor i identificador.

Si no existeix cap subconjunt de quatre candidates que compleixi totes les
restriccions, la decisió és `REJECT`. No es relaxen els llindars després de veure
els resultats.

## Evidència utilitzada

Cada candidata ha d'arribar d'un artefacte `small_account_economics` amb `PASS`,
exactament 200 USDC, costos Ostium congelats i un trace schema 2 reproduïble.
El trace conserva ara entrada i sortida UTC, stop inicial reconstruït i PnL net
d'estrès. La correlació alinea la unió de dates i posa zero quan una estratègia
no tanca cap operació aquell dia.

No s'accedeix al holdout final, ni s'autoritza paper o live.

Els mateixos límits es tornen a calcular abans de cada ordre paper amb
`portfolio_entry_admission_v4.py`. Una instrucció de sizing no pot avançar si
la projecció crea una tercera posició, supera el 3% de risc de stop, compromet
més del 60% de l'equity actual o repeteix una candidata ja activa. Aquesta
funció és pura: retorna `PASS` o `BLOCK`, però no envia cap ordre.

## Registre global i terminalitat

`portfolio_registry_v4.json` és l'inventari preregistrat de campanyes. Es pot
ampliar només abans de consultar el rendiment de la campanya nova; una campanya
ja registrada no s'elimina perquè fracassi. Mentre `registration_closed=false`,
el coordinador publica `WAITING_FOR_REGISTRATION_CLOSE` i no crea cap manifest.

El primer univers queda tancat abans de veure cap rendiment v4 amb sis
campanyes: EURUSD D1, USDJPY M15, XAUUSD M15, BTCUSD H4, ETHUSD H4 i US500 D1.
La selecció es basa només en executabilitat potencial a Ostium, disponibilitat
de dades i diversificació entre forex, metall, cripto i índex. Cada campanya té
tres mecanismes i les direccions `both/long/short` congelades a
`campaign_universe_v4.json`. Mapping o costos immadurs mantenen la campanya en
espera; no autoritzen substituir-la després de veure resultats.

Per cada `campaign_root`, `portfolio_coordinator_v4.py` recorre en ordre els
rebuts screen, SQ, temporal, robustesa i compte petit. Un rebuig en qualsevol
etapa és terminal i forma part de l'evidència global. Només un `PASS_SMALL_ACCOUNT`
aporta una candidata. El coordinador espera totes les campanyes registrades i
rebutja rebuts posteriors a un rebuig terminal; així no es pot construir la
cartera només amb els experiments favorables.

Execució idempotent:

```bash
PYTHONPATH=. .venv/bin/python -m lab.sq_bridge.portfolio_coordinator_v4
```

La sortida durable és `data/alquimia_v4/portfolio/portfolio_coordinator_status.json`.
Quan el registre està tancat i totes les campanyes són terminals, crea el
manifest i executa automàticament la construcció de cartera. El worker de
holdout reobre i recomputa l'artefacte, i exigeix que la candidata i el hash
exacte del seu sizing constin en la cartera seleccionada.

Els workers post-SQ comparteixen un contracte de mercat obligatori dins la seva
configuració: `symbol`, `timeframe`, `source_timezone`, `ostium_pair_id`,
`ostium_pair_from`, `ostium_pair_to` i `ostium_category`. La validació temporal
el contrasta amb el manifest CFX; sizing i paritat amb les candles; robustesa
amb l'instrument observat als costos. Un `overnightMaxLeverage=0` significa que
l'override de day trading d'accions no aplica en forex, cripto, commodities i
índexs. En accions cal un límit overnight positiu observat i s'usa el mínim
entre límit general i overnight. Això permet reutilitzar la cadena en altres
tokens sense substituir manualment literals d'EURUSD ni assumir un
apalancament incorrecte.

Font operacional: documentació oficial d'[Ostium Markets](https://docs.ostium.com/traders/reference/markets),
que limita l'overnight cap i l'auto-close de 15:45 ET a les posicions d'accions
obertes per sobre del cap, mentre cripto opera 24/7.

## Manifest de campanya

```json
{
  "schema_version": 1,
  "portfolio_id": "alquimia-v4-small-account-portfolio",
  "holdout_accessed": false,
  "small_account_branches": [
    {
      "hypothesis_id": "d1_breakout_long",
      "campaign_id": "eurusd-d1-alquimia-v4",
      "artifact_path": "/ruta/06_small_account_economics.json",
      "artifact_sha256": "..."
    }
  ]
}
```

Execució determinista:

```bash
PYTHONPATH=. .venv/bin/python -m lab.sq_bridge.portfolio_construction_v4 \
  --manifest /ruta/portfolio_manifest.json \
  --output /ruta/portfolio_construction.json
```

El manifest definitiu només es crea quan el registre està tancat i totes les
campanyes han arribat a PASS de compte petit o a un rebuig terminal anterior.
