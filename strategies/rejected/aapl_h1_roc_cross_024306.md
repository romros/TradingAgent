# AAPL H1 ROC-cross 0.24306 — rebutjada per fragilitat

## Decisió

`REJECT_PARAMETER_ROBUSTNESS`. L'estratègia mostrava edge estadístic en la
validació 2023 i l'OOS 2024, però no ha superat el Monte Carlo paramètric natiu
de StrategyQuant. No entra a la llibreria consolidada, a cap cartera, paper ni
LIVE.

## Regla congelada

- Actiu: Apple (`AAPL`), timeframe H1, només long i màxim una posició.
- `ROC(227)[1]` creua per sota de `ROC(213)[3]`.
- `ROC(162)[2]` cau estrictament durant tres barres.
- Entrada a mercat a la barra següent.
- Stop `4,0 × ATR(30)` i target `2,4 × ATR(30)`.
- Sense trailing, break-even, EOD ni sortida temporal explícita.
- Semàntica intrabar d'SQ amb precisió tick.

SHA-256 de l'arbre SQ congelat:
`6cbf07564f2c59a1ae54c65d6c5fc848c81ecfed9c302c1cf78230f1e5c90d7d`.

## Per què semblava bona

- Validació 2023: 29 trades, mitjana bruta +0,710%, PF 2,251.
- OOS 2024: 24 trades, mitjana bruta +0,351%, PF 1,454.
- Conjunt: 53 trades, mitjana +0,548%, PF 1,829 i t=2,099.
- Bootstrap determinista: 98,0% de mostres amb mitjana positiva.
- OOS indicatiu amb 1.000 USD i IBKR tiered: +5,388%, PF 1,308,
  DD 8,03%.

## Prova que la rebutja

Abans de veure el resultat es va congelar una prova sobre 2020-08-31..2024-12-31:
1.000 simulacions natives `RandomizeStrategyParameters`, probabilitat 100% i
canvi màxim ±10%. SQ va executar el cross-check i va persistir 999 variants
més el resultat original, però la candidata va quedar `Failed` (0 passades,
1 fallida). No va satisfer l'acceptació nativa al nivell de confiança 80%:
benefici Monte Carlo com a mínim igual al 50% del principal i DD com a màxim
el 200% del principal.

La concentració ja advertia del problema: els tres millors trades equivalien
aproximadament al 99% del benefici net OOS 2024 i l'escenari stress 2024 era
−1,98%. La combinació d'aquests indicis amb el fracàs paramètric és suficient
per rebutjar-la; no s'optimitza ni s'obre el holdout 2025+.

Evidència:

- `data/ibkr_sq_v2/aapl_h1_shock_reversion_tiered_pilot/aapl_024306_statistical_edge_gate_v1.json`
- `data/ibkr_sq_v2/aapl_h1_shock_reversion_tiered_pilot/robustness_prehold/0_24306/robustness_gate.preregistered.json`
- `data/ibkr_sq_v2/aapl_h1_shock_reversion_tiered_pilot/robustness_prehold/0_24306/run/sq_retest_final.log`
- SQX natiu: projecte `IBKR_V2_AAPL_H1_MC_PREHOLD_0_24306`, databank
  `PreHoldout`.

## Aprenentatge reutilitzable

No tornar a promocionar regles intraday amb períodes llargs i molt específics
només perquè passen validació/OOS. En futures cerques, el veïnat paramètric
entra abans de la promoció i es prioritzen regles simples, zones amples de
paràmetres i contribució de beneficis menys concentrada.
