# Estat operatiu d'Alquímia

Aquest és el punt d'entrada curt. Si un fitxer antic contradiu aquest estat, manen
l'objectiu i el catàleg enllaçats aquí; els manifests antics es conserven només com
a traça de decisions.

## Objectiu vigent

- Capital principal: 500 USDC a Ostium.
- Target de recerca: estudiar 500→1.000 en uns dotze mesos, sense prometre'l.
- Univers: EUR/USD, US500/USD i XAU/USD.
- Cartera: entre 1 i 6 estratègies; usar el conjunt més petit que superi costos i
  risc. Preferir 3–6 només si aporten diversificació mesurable.
- Límits: drawdown 15%, risc simultani 3% i leverage efectiu 5x.

Font canònica: `packages/strategyquant/ostium-500-objective.json`.

## Estat actual

- 0 components promocionables.
- 23 famílies rebutjades.
- Simulació de cartera bloquejada fins que existeixi almenys un component net.
- Holdout 2025-08-01/2026-07-31 segellat.

Consultar l'estat executable, que té prioritat sobre aquest resum:

```bash
python3 academia/tools/ostium_objective_status.py
```

Font canònica: `packages/strategyquant/ostium-500-strategy-catalog.json`.

## Única feina activa

Acabar el gate de costos d'execució d'US500/USD: després de la mostra d'obertura
qualificada del 2026-08-11, falten migdia i tancament del mateix dia i les tres
franges de dos dies addicionals. No iniciar una altra família ni usar SQCLI fins
que aquest gate doni una decisió.

Si passa, provar una família de baixa rotació basada en prima de risc, amb
volatilitat només com a estat de risc congelat. Si falla, registrar el límit
econòmic i no generar variants M15.

## Què no és actiu

Els altres manifests de `experiments/pending/` poden ser preregistres tancats,
cancel·lats, bloquejats o substituïts. No són una cua de feina. En particular:

- BTC està cancel·lat per decisió d'abast de l'usuari.
- Les versions `3v4`, `3v5` i `3v6` de cartera estan substituïdes per
  `ostium-500-portfolio-3asset-v1.json`.
- Les famílies que apareixen a `rejected_families` del catàleg no s'han de repetir
  ni invertir sense un mecanisme causal nou.
- `runtime/` és material local regenerable i ignorat per Git; no és coneixement
  canònic ni s'ha de consultar per decidir l'estat del projecte.

## Mapa mínim

- `packages/strategyquant/`: objectiu, catàleg i cobertura SQ.
- `experiments/observations/`: evidències transformades i decisions.
- `experiments/failure-memory.json`: errors que no s'han de repetir.
- `skills/strategyquant-alquimia/`: coneixement executable per a l'agent.
- `courses/strategyquant/`: explicació humana.
- `sources/`: procedència i drets, no conclusions operatives.

