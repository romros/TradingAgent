# AAPL H1 ROC-cross 0.24306

## Estat

`PASS_STATISTICAL_RESEARCH_EDGE`. És una cinquena estratègia de recerca, no una
autorització paper ni LIVE. Va ser descoberta per SQ sobre 2020-08-31..2022,
seleccionada amb 2023 i oberta una sola vegada sobre OOS 2024 sense modificar
la regla.

## Regla determinista

- Actiu: Apple (`AAPL`), timeframe H1, només long i màxim una posició.
- Al tancament de barra, `ROC(227)[1]` creua per sota de `ROC(213)[3]`.
- Simultàniament, `ROC(162)[2]` ha de caure estrictament durant 3 barres.
- Entrada a mercat a la barra següent.
- Stop: `4,0 × ATR(30)`; target: `2,4 × ATR(30)`.
- Sense trailing, break-even, sortida EOD ni sortida temporal explícita.
- `MaxTradesPerDay=1`; semàntica intrabar d'SQ amb precisió tick.

La identitat de l'arbre SQ és
`6cbf07564f2c59d9adc5fc768d5fcf848c81ecfed9c302c1cf78230f1e5c90d7d`.
L'SQX canònic validat és al projecte
`IBKR_V2_AAPL_H1_VAL_0_24306/databanks/Validation/Strategy 0.24306.sqx`.

## Evidència

- Validació 2023: 29 trades, mitjana bruta +0,710%, PF 2,251, t=2,104.
- OOS 2024: 24 trades, mitjana bruta +0,351%, PF 1,454.
- Conjunt: 53 trades, mitjana +0,548%, PF 1,829, t=2,099.
- Bootstrap determinista de 10.000 mostres: 98,0% amb mitjana positiva.
- Eliminant els tres millors trades: mitjana encara +0,434% en 50 trades.
- OOS a 1.000 USD, accions senceres i IBKR tiered indicatiu: +5,388%,
  PF 1,308 i DD 8,03%.
- Stress compost validació+OOS: +5,409%.

Gate final:
`data/ibkr_sq_v2/aapl_h1_shock_reversion_tiered_pilot/aapl_024306_statistical_edge_gate_v1.json`.
Els rebuts natius i ordres són a
`data/ibkr_sq_v2/aapl_h1_shock_reversion_tiered_pilot/{validation,oos}/0_24306/`.

## Limitacions i treball pendent

El 2024 tiered és molt concentrat: els tres millors trades equivalen al 99% del
benefici net anual, i l'escenari stress 2024 és −1,98%. La prova d'eliminació
dels tres guanyadors passa només quan s'uneixen 2023 i 2024. A més, els períodes
ROC són específics i encara falta demostrar una regió paramètrica estable.

Abans d'incorporar-la a una cartera cal: traducció Python, paritat de senyals i
trades SQ↔Python, veïnat paramètric preregistrat, límit temporal de posició,
correlació amb les quatre sleeves actuals i holdout 2025+ segellat. Fins llavors
`paper_authorized=false` i `live_authorized=false`.
