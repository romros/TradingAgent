# MSFT D1 Capitulation

- Identificador: `msft_d1_capitulation`
- Actiu: Microsoft (`MSFT`)
- Timeframe: D1
- Mecanisme: reversió oportunista després d'un xoc de venda
- Estat: `ADMITTED_RESEARCH_EDGE`
- Paper/LIVE: no autoritzat

## Evidència principal

- Paritat SQ/Python:
  `data/ibkr_sq_v2/msft_capitulation_native/retest/run/signal_parity_receipt_v1.json`
- Evidència de cartera:
  `data/ibkr_sq_v2/three_strategy_portfolio/sxr8_cat_msft_v1.json`
- Catàleg canònic: `lab/sq_bridge/theoretical_strategy_library_v1.json`

## Limitació principal

La paritat de senyals és exacta, però els períodes històrics disponibles no
constitueixen un holdout nou completament verge. Cal mantenir aquesta limitació
en qualsevol estimació de rendiment.

