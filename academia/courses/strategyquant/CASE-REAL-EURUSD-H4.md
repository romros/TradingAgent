# Cas real: un bon OOS que no sobreviu als costos

## Què semblava prometedor

`Strategy 4.1.133`, EURUSD H4, supera el gate temporal d'Alquímia:

- 138 trades;
- Profit Factor 1,25;
- R Expectancy 0,13;
- degradació d'expectativa 18,75%;
- drawdown normalitzat 11,55%;
- tots els checks temporals passen.

Mirant només aquesta fase, l'agent podria dir «continuar».

## Què passa quan entra l'economia real del compte

Amb l'escenari base de 4,5 bps round trip i 0,10 USDC fixos:

- PnL net: -19,81 USDC;
- expectativa: -0,144 USDC per trade;
- Profit Factor net: 0,51;
- drawdown: 23,85 USDC;
- només 0,2% de 1.000 simulacions Monte Carlo acaben rendibles.

I això encara exclou rollover. Per tant, no és un escenari exageradament hostil.

## Decisió de l'expert

```text
DECISIÓ: DESCARTAR
MOTIU: passa la validació temporal, però l'edge desapareix amb els costos base.
RISC PRINCIPAL: moviment brut insuficient per trade per a un compte petit.
SEGÜENT PAS: canviar la font d'edge o reduir fricció estructural; no afinar paràmetres.
EVIDÈNCIA: alquimia-eurusd-h4-2026-08 / TEMPORAL_PASS_COST_FAIL
```

## Insight après

Un gate temporal i un cost gate no són duplicats. El primer pregunta si el patró es
manté en el temps; el segon si aquest patró és econòmicament capturable. Aquí la
resposta és «sí» al primer i «no» al segon.

L'acció correcta no és buscar una WFM millor, més leverage o un llindar una mica
diferent. Amb 138 trades, el cost converteix PF 1,25 en 0,51: és un problema
estructural d'economia per trade.

## Traçabilitat

Fitxa normalitzada:
`academia/experiments/observations/alquimia-eurusd-h4-2026-08.json`.

Artifacts originals només llegits:

- `lab/out/alquimia/ALQUIMIA_EURUSD_H4_OOS/oos_gate.json`
- `lab/out/alquimia/ALQUIMIA_EURUSD_H4_OOS/trade_cost_gate_eurusd.json`
