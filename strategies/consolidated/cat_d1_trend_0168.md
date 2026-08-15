# CAT D1 Trend 0.168

## Contracte executable

- Actiu: Caterpillar (`CAT`), recurs SQ `CAT_IBKR_V2_D1`.
- Timeframe: D1, zona horària/session NYSE de la font canònica Dukascopy.
- Direcció: només long; una posició simultània.
- Entrada: mercat quan la línia `2` d'`ADX(40)` creua per sota d'ella
  mateixa entre `shift=3` i `shift=2` (`CrossesBelow(ADX(40, line 2,
  shift 2), ADX(40, line 2, shift 3))`). Aquesta forma aparentment redundant
  és la representació literal extreta de SQ; no s'ha de reinterpretar sense
  una nova prova de paritat.
- Stop-loss: `2.5 × ATR(30)` des del preu d'entrada.
- Profit-target: `2.1 × ATR(30)` des del preu d'entrada.
- Sortida temporal: desactivada (`ExitAfterBars=0`).
- EOD i divendres: desactivats. Cap trailing stop ni break-even.
- Costos dins SQ: zero; s'apliquen després amb l'auditor IBKR.

## Reconstrucció en StrategyQuant

1. Importar la font D1 canònica de CAT amb `pointValue=1`,
   `orderSizeMultiplier=1`, `orderSizeStep=1`, `tickStep=0.001`, spread zero.
2. Crear una estratègia long amb una única condició d'entrada i els dos exits
   ATR indicats. Desactivar totes les sortides horàries i `ExitAtEndOfDay`.
3. Fer el retest amb mida fixa d'una acció i exportar les ordres.
4. Comparar senyals/ordres amb els rebuts `parity_0_168.json` abans de mirar
   rendiment. Una diferència de dates significa que la reconstrucció no és
   equivalent.
5. Aplicar fora de SQ els plans IBKR tiered, fixed i stress. No incorporar
   retrospectivament aquests costos canviant la lògica.

L'SQX original encara existeix en artefactes SQ, però aquesta fitxa i
`sqx_extract.py` permeten reconstruir-lo si s'esborren.

## Evidència i resultat

- OOS 2024, 1.000 $, stress: 21 operacions, +13,23%, PF 1,333, win rate
  61,9%, DD close-to-close 15,81%.
- Mediana de durada: 264 hores; màxim 720 hores.
- Evidència: `data/ibkr_sq_v2/cat_d1_trend_pilot/oos/audit_0_168.json`.
- Paritat: `data/ibkr_sq_v2/cat_d1_trend_pilot/oos/parity_0_168.json`.
- Robustesa/Monte Carlo: `data/ibkr_sq_v2/cat_d1_trend_pilot/pre_holdout/`.

## Limitacions

És un edge específic de CAT: la transferència congelada a DE, UNP i CMI va
fallar. L'extractor classifica `ADX` fora del subset Python traduïble actual;
per això la comprovació nativa SQ i els rebuts són obligatoris. Recerca admesa,
paper i LIVE no autoritzats.

