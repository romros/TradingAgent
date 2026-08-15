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

Això valida agregació, calendari, solapament i diversificació dins SQ. El pas
següent ja també està resolt: Portfolio Composer, amb el mètode custom
`AlquimiaFixedBudgetFloor`, aplica quatre compartiments fixos de 500 USD i
`floor(500/preu)` en accions senceres. Accepta 93 ordres úniques, cap notional
supera 500 USD (màxim 499,45), i dona **+32,91% brut** amb **DD diari 5,80%**.
SQ continua amb costos neutres; no és encara l'economia neta IBKR. Evidència:
`data/ibkr_sq_v2/four_edge_portfolio_composer_v1/`.

La correcció pre-compte usa el creuament oficial ECB GBP/EUR i USD/EUR. Detecta
que SQ tractava erròniament 27,73 GBP com 27,73 USD: el sleeve SGLN correcte és
13 unitats, no 18. El brut corregit baixa a **+30,26%**. Amb comissions i
fricció indicatives, el total 2022–2024 és **+26,13% tiered**, **+18,83% fixed**
i **+17,02% estrès**. L'estrès són 340,47 USD en tres anys sobre 2.000 USD,
aproximadament 5,3% anualitzat. Sense compte no es pot confirmar el pla, venue,
KID ni comissió del fill real; per això continua sent un gate teòric.

La paritat agregada troba exactament **93/93 entrades**: CAT 57, MSFT 15,
JPM 20 i SGLN 1. El log SQ repetia literalment l'última ordre CAT i explicava
el recompte antic de 94. CAT/JPM/SGLN coincideixen també en preu; MSFT només
en dates perquè Python usa preus ajustats i SQ preus nominals, límit ja declarat
en la seva auditoria individual.

## Cadena pendent, en ordre

1. **Completat:** D1 ajustat de SGLN importat amb GBp dividit per 100. Són
   3.283 files, 2012-01-03–2024-12-31; el round-trip SQ conserva tots els
   timestamps i arrodoneix OHLC com a màxim 0,00005049 GBP.
2. **Completat:** retest SGLN 2019–2024 i paritat exacta dates/preus 3/3.
3. **Completat:** Portfolio Master 4-de-4 sobre finestra comuna 2022–2024.
4. **Completat:** Portfolio Composer amb pesos fixos 25%, pressupost 500 USD,
   unitats senceres floor i auditoria de totes les ordres.
5. **Completat provisionalment sense compte:** FX històric i tres escenaris de
   costos públics. Pendent substituir-los per fills/statement quan hi hagi compte.
6. **Completat per entrades:** 93/93 dates; preu exacte CAT/JPM/SGLN i abast
   explícit només de senyal per MSFT. Les sortides depenen dels rebuts individuals.

## Límits que una sessió nova no pot reinterpretar

- SGLN va fallar el gate standalone de DD; només és admissible amb pes màxim
  del 25%.
- El +28,26% anterior era amb quatre sleeves de 1.000, no 1.000 total.
- El +21,99% a 2.000 és històric, closed-equity i amb FX aproximat 1:1.
- Portfolio Composer ja resol el sizing brut. El MM integrat de SQ queda
  rebutjat perquè arrodonia cap amunt i podia gastar més de 500 USD.
- Encara falta substituir costos públics per comissions/fills del compte real.
- `paper_authorized=false` i `live_authorized=false` fins completar els gates.
