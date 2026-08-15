# Cartera de quatre edges — estat canònic

Aquest és el punt d'entrada per reprendre el projecte sense reconstruir el fil.
L'objectiu vigent és una llibreria de 4–8 estratègies amb edge estadístic i una
cartera executable a IBKR. No s'ha autoritzat ni paper ni LIVE.

## Peces consolidades

| Peça | Regla resumida | Evidència | SQ natiu | Estat |
|---|---|---|---|---|
| CAT 0.168 | Pullback/trend D1 amb DI/ATR congelats | OOS 2024 i transferències documentades | Sí | Reserva consolidada |
| MSFT capitulation | Caiguda diària >2% sota BB(20,2), compra open i sortida close | Paritat nativa i costos | Sí | Consolidada |
| JPM Momentum60 | Canvi de mes i `Close[1] > Close[61]`, hold 20 | OOS natiu + confirmació recent | Sí | Consolidada |
| SGLN TSMOM12 | A primer dia de mes, long si últim final de mes supera l'exacte de fa 12 mesos; altrament cash | Confirmació SGLN/PHAU; només sleeve ≤25% | Sí; paritat exacta de 3/3 trades | Condicional |

Les fitxes detallades viuen a `strategies/consolidated/`. Els intents que no
passen viuen a `strategies/rejected/README.md` i no s'han de regenerar sense una
hipòtesi materialment diferent.

## Capital petit

La graella canònica és
`data/ibkr_sq_v2/gold_tsmom_confirmation_v1/four_strategy_small_account_v1.json`.
Amb unitats senceres i quatre compartiments fixos del 25%, 2.000 és el primer
punt provat que executa les quatre peces. Amb 500 només s'executa l'or; amb
1.000 o 1.500 CAT queda fora. És un diagnòstic 2022–2024, no una promesa.

## SGLN natiu — treball completat

No s'ha substituït la regla mensual per `Close[252]` ni `Close[253]`. El bloc
Java detecta el primer trading bar del mes i localitza el final de mes del
calendari de fa exactament 12 mesos. Els fonts versionats són a
`lab/sq_bridge/sq_extensions/`; les còpies instal·lades són a
`/mnt/volume-SQ/user/extend/Snippets/`.

El 2026-08-15:

1. els tres fonts compilen contra les llibreries reals SQ 143.2708;
2. s'ha preservat el `Snippets.jar` anterior a
   `/mnt/volume-SQ/user/backups/sgln_tsmom12_native_v1/preinstall_20260815/`;
3. SQCLI ha regenerat el JAR i les tres classes hi són;
4. s'ha creat `SGLN_TSMOM12_MONTHLY_NATIVE_V1.sqx` sense resultats heretats;
5. no s'ha accedit a performance nativa.

SQ documenta oficialment els snippets Java extensibles i Portfolio Composer:

- https://strategyquant.com/doc/programming-for-sq/adding-indicators-and-signals/
- https://strategyquant.com/doc/strategyquant/portfolio-composer/

## Resultat de cartera SQ nativa

Les quatre peces s'han retestat sobre la mateixa finestra 2022–2024 i Portfolio
Master ha generat l'única combinació 4-de-4 possible. La corba diària nativa
acaba a **+13,52%** sobre 2.000 i té **3,17%** de drawdown mark-to-market.
El balanç tancat exportat acaba a 2.276,56
(+13,83%). Les quatre `PortfolioParts` són dins l'SQX.

Això valida agregació, calendari, solapament i diversificació dins SQ, però no
és encara la configuració ideal de capital: Portfolio Master ha usat una acció
sencera per entrada, no quatre compartiments fixos del 25%, i costos SQ neutres.
Per això no substitueix el diagnòstic Python de +21,99%/DD 8,47%; respon una
pregunta diferent. Evidència: `data/ibkr_sq_v2/four_edge_portfolio_master_v1/`.

## Cadena pendent, en ordre

1. **Completat:** D1 ajustat de SGLN importat amb GBp dividit per 100. Són
   3.283 files, 2012-01-03–2024-12-31; el round-trip SQ conserva tots els
   timestamps i arrodoneix OHLC com a màxim 0,00005049 GBP.
2. **Completat:** retest SGLN 2019–2024 i paritat exacta dates/preus 3/3.
3. **Completat:** Portfolio Master 4-de-4 sobre finestra comuna 2022–2024.
4. Implementar en SQ/Portfolio Composer els pesos fixos 25% o demostrar una
   equivalència exacta; després aplicar costos IBKR i FX GBP/USD.
5. Resoldre a IBKR `IE00B4ND3602`, listing, moneda, KID i comissió.
6. Comparar trade-a-trade la cartera ponderada SQ contra Python i només llavors
   decidir si mereix shadow/paper.

## Límits que una sessió nova no pot reinterpretar

- SGLN va fallar el gate standalone de DD; només és admissible amb pes màxim
  del 25%.
- El +28,26% anterior era amb quatre sleeves de 1.000, no 1.000 total.
- El +21,99% a 2.000 és històric, closed-equity i amb FX aproximat 1:1.
- Portfolio Master ja ha passat l'auditoria comuna de rendiment, però amb una
  acció per trade i costos neutres; encara no és sizing operable.
- `paper_authorized=false` i `live_authorized=false` fins completar els gates.
