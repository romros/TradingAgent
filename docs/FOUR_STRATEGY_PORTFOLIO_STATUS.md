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
| SGLN TSMOM12 | A primer dia de mes, long si últim final de mes supera l'exacte de fa 12 mesos; altrament cash | Confirmació SGLN/PHAU; només sleeve ≤25% | Shell i blocs instal·lats; paritat pendent | Condicional |

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

## Cadena pendent, en ordre

1. **Completat:** D1 ajustat de SGLN importat amb GBp dividit per 100. Són
   3.283 files, 2012-01-03–2024-12-31; el round-trip SQ conserva tots els
   timestamps i arrodoneix OHLC com a màxim 0,00005049 GBP.
2. Retestar l'SQX sobre 2019–2024 sense canviar la regla.
3. Exportar ordres i exigir paritat de dates/estats amb Python; sizing i costos
   es comparen separadament.
4. Resoldre a IBKR `IE00B4ND3602`, listing, moneda, KID i comissió.
5. Executar Portfolio Master/Composer amb les quatre peces paritàries.
6. Comparar ordres omeses, solapament, equity i DD mark-to-market amb Python.

## Límits que una sessió nova no pot reinterpretar

- SGLN va fallar el gate standalone de DD; només és admissible amb pes màxim
  del 25%.
- El +28,26% anterior era amb quatre sleeves de 1.000, no 1.000 total.
- El +21,99% a 2.000 és històric, closed-equity i amb FX aproximat 1:1.
- Portfolio Master ha passat un smoke de capacitat, no de rendiment.
- `paper_authorized=false` i `live_authorized=false` fins completar els gates.
