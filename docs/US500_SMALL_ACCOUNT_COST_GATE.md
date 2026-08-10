# US500 — gate de costos per a compte petit

## Estat

`BLOCK_INSUFFICIENT_EXECUTION_COVERAGE`. El transformador està preregistrat,
però no pot congelar cap cost fins que el resum d'Ostium contingui 20 quotes a
open, midday i close, distribuïdes durant almenys 30 minuts, en cadascun de tres
dies complets de Nova York.

## Entrada i sortida

`academia/tools/summarize_execution_quotes.py` resumeix només observacions
read-only de l'SDK oficial. `lab/sq_bridge/spxusd_small_account_cost_gate.py`
consumeix aquest resum i falla tancat si no té cobertura o si falta qualsevol
dels nocionals 60, 100, 200, 400 i 500 USDC. La sortida no autoritza mai paper
ni live; només congela inputs reproduïbles per al backtest posterior.

El cron captura dues quotes cada cinc minuts. Això evita confondre vint lectures
en quaranta segons amb vint observacions de la finestra. Quan el gate ja passa,
els dies parcials posteriors queden fora de les estadístiques congelades.

Per cada nocional, el proxy round-trip mesurat és:

`spread complet + fee d'obertura + fee de tancament + impacte long + impacte short`

Els escenaris preregistrats són:

- base: mediana del proxy;
- conservador: p95 del proxy;
- estrès: màxim entre dues vegades la mediana i el p95, més la pèrdua dels
  0,10 USDC bloquejats per l'oracle.

L'oracle es considera reemborsat en base i conservador després d'un full close
correcte. Cobrar-lo sempre seria una penalització falsa, especialment a 200
USDC; l'estrès sí que modela una fallada del reemborsament. El rollover negatiu
observat no es converteix en benefici històric: es limita a zero. Conservador i
estrès mantenen els falsadors preregistrats del 8% i 12% anual com a mínim.

## Separació respecte de l'apalancament

Aquest gate estima fricció sobre el nocional de la posició, no decideix
apalancament. La selecció posterior haurà de limitar el nocional simultàniament
per risc a stop/MAE, marge disponible, liquidació exacta d'Ostium i el màxim
vigent del venue. Que Ostium permeti 100x no converteix 100x en apalancament
segur ni rendible.

## Execució reproduïble

```bash
python academia/tools/summarize_execution_quotes.py RAW.jsonl --output SUMMARY.json
python lab/sq_bridge/spxusd_small_account_cost_gate.py \
  --summary SUMMARY.json --output COSTS.json
```

Mentre `SUMMARY.json` no sigui `MEASURED`, la segona ordre produeix
`BLOCK_INSUFFICIENT_EXECUTION_COVERAGE` i no fabrica valors substitutius.
