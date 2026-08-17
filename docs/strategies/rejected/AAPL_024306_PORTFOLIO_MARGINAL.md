# AAPL H1 0.24306 — edge de recerca, no cinquena pota

## Veredicte

`Strategy 0.24306` es conserva com a **edge estadístic de recerca**, però queda
**rebutjada com a cinquena pota de la cartera consolidada de 2.000 USD**. No és
una contradicció: una regla pot tenir senyal brut i, alhora, empitjorar una
cartera concreta després de mida executable, costos i finançament.

## Regla congelada

- Actiu i marc: AAPL, H1, només long.
- Entrada: `CrossBelow(ROC(227)[1], ROC(213)[3])` i `ROC(162)` decreix durant
  tres barres.
- Sortida: profit target `2,4 × ATR(30)` i stop loss `4,0 × ATR(30)`.
- Execució nativa SQ amb dades TICK; no es declara paritat exacta amb una
  reconstrucció Python H1.

## Evidència a favor

- Validació 2023: 29 trades, PF brut 2,251.
- OOS 2024: 24 trades, PF brut 1,454.
- Combinat: 53 trades, mitjana +0,548%, PF 1,829 i t=2,099.
- Monte Carlo natiu de paràmetres: 1.000 simulacions, 93,9% rendibles, mediana
  +0,55355%, percentil 5 −0,034805% i 0% de simulacions sense trades. El decoder
  valida el payload compacte contra les 111 ordres originals de SQ.

## Per què no entra a la cartera

La prova marginal congela la cartera base de quatre edges, li dona prioritat i
afegeix una sola màniga AAPL limitada a 500 USD. Aplica 10 bps per costat,
1 USD per ordre i 8% anual només sobre capital prestat mentre la posició és
oberta.

Resultat 2022–2024:

- AAPL: −57,22 USD nets, PF 0,695 i 20,66 USD de finançament.
- Cartera base: +56,0418%, CAGR 15,9996%, DD 15,9160%.
- Amb AAPL: +53,1807%, CAGR 15,2858%, DD 15,9160%.

AAPL no millora el CAGR, no redueix el drawdown i el seu PnL marginal és
negatiu. No s'optimitza per forçar-ne l'admissió.

## Reproducció

- Motor MC: `lab/sq_bridge/aapl_024306_native_mc_gate_v1.py`
- Rebut MC: `data/ibkr_sq_v2/aapl_h1_shock_reversion_tiered_pilot/robustness_prehold/0_24306/native_mc_gate_v1.json`
- Motor marginal: `lab/sq_bridge/aapl_024306_residual_margin_portfolio_v1.py`
- Rebut marginal: `data/ibkr_sq_v2/aapl_h1_shock_reversion_tiered_pilot/aapl_024306_residual_margin_portfolio_v1.json`

No autoritza paper ni live. Si es reobre algun dia, haurà de ser per una
hipòtesi nova preregistrada o una economia de compte materialment diferent, no
per ajustar paràmetres mirant aquests resultats.
