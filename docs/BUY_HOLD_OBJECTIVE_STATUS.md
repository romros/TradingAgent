# Objectiu vigent: superar buy-and-hold

## Resultat actual

La primera cartera que supera el benchmark passiu estàndard és una **candidata
de recerca**, no una cartera consolidada ni autoritzada:

| Sleeve | Capital |
|---|---:|
| CAT 0.168 | 500 USD |
| MSFT capitulation | 500 USD |
| JPM Momentum60 | 500 USD |
| SGLN TSMOM12 | 500 USD |
| NFLX 0.4681 | 1.000 USD |

Entre 2022 i 2024, amb accions senceres, sense palanquejament, sense
transferències entre sleeves i costos d'estrès:

- cartera: +32,04%, CAGR 9,71%, drawdown diari MTM 7,09%;
- SPY buy-and-hold: +26,96%, CAGR 8,29%, drawdown 23,40%;
- buy-and-hold dels mateixos cinc actius i pesos: +44,65%, CAGR 13,10%,
  drawdown mensual 22,70%.

Decisió exacta: `PASS_FOUR_EDGE_NFLX_BEATS_SPY_BUY_HOLD`. La cartera supera
SPY tant en retorn com en drawdown, però **no** supera comprar i mantenir els
mateixos actius. Les dues comparacions es mostren per evitar cherry-picking.

## Bloqueig que no es pot reinterpretar

NFLX 0.4681 continua fora de `strategies/consolidated`: el centre té paritat
68/68, auditoria M1 i resiliència estadística favorables, però el veïnat va
fallar el gate de drawdown paramètric congelat. El shadow forward és una via
legítima per obtenir evidència nova; el bon resultat de cartera no rescata
retroactivament aquell gate.

Per tant, el resultat completa una fita de construcció de cartera però no
autoritza paper ni live. `paper_authorized=false` i `live_authorized=false`.

## Evidència reproduïble

- `lab/sq_bridge/four_edge_nflx_daily_mtm_v1.py`
- `lab/sq_bridge/four_edge_nflx_daily_mtm_v1.json`
- `data/ibkr_sq_v2/portfolio_benchmark_v1/four_edge_nflx_daily_mtm_v1.json`
- `lab/sq_bridge/three_edge_vs_weighted_buy_hold_v1.py`
- `lab/sq_bridge/nflx_marginal_portfolio_v1.py`

## Passos següents

1. Acumular shadow NFLX sense canviar la regla.
2. Incorporar JPM i SGLN al mateix monitor shadow.
3. Cercar una nova família consolidable que pugui substituir NFLX si la seva
   robustesa forward no confirma l'edge.
4. Repetir la comparació contra SPY i contra mateixos actius abans de qualsevol
   promoció.

La primera sincronització va informar erròniament 15,37% de drawdown per un
carry-forward antic en un dia sense posició NFLX. La màquina d'estats
cronològica corregida, protegida per test de regressió, dona 7,09%. L'endpoint
no va canviar. El valor antic no s'ha de reutilitzar.
