# Campanya ETF i tech transfer — 2026-08-15

Objectiu: trobar un edge addicional sense modificar paràmetres després de
veure resultats. Cap família d'aquesta campanya entra al catàleg consolidat.

## Famílies rebutjades

- IWM D1 short-term reversal: cap regió estable al train; el millor punt amb
  mostra suficient tenia PF aproximat 0,975.
- XLE/EEM time-series momentum mensual 6/12 mesos: XLE va passar validació
  però va perdre a OOS 2024; EEM ja va fallar validació.
- Rotació relativa 3/6/12 mesos IWM/EEM/EFA/XLE/XLF: la finestra central de
  126 sessions va perdre a train i validació.
- Momentum 12–1 long-only: sobre CFD raw semblava passar OOS (+35,64%), però
  amb OHLC ajustat per dividends/splits el train va ser −18,00% i l'acord de
  selecció entre fonts només 83,33% al train i 81,82% el 2024. Decisió:
  `REJECT_SOURCE_DEPENDENT`.
- Tendència diversificada de 8/10/12 mesos: totes tres variants van perdre el
  2022–2023 (−3,19%, −2,70%, −6,20%).
- Momentum60 exacte sobre ETFs: cap dels cinc actius va passar train,
  validació i OOS.
- Momentum60 exacte sobre AMZN/GOOG/META/NVDA/AVGO: GOOG i AVGO van obrir el
  holdout recent. GOOG va fer +10,04% i PF 1,305, però DD 26,34% contra gate
  25%; AVGO va fer −15,48%, PF 0,905 i DD 35,76%. No es relaxa el gate.
- QQQ turn-of-month `last 1 + first 3`: +5,65% net el 2022–2024 i PF 1,214,
  però Sharpe 0,254 contra gate 0,50.
- ETF 12–1 long-short: train −24,95%; família tancada.

## Watchlist no promocionable

JPM SQ Strategy 0.24 conserva validació stress +17,64%, PF 1,469 i DD 18,94%,
però només 24 trades. El mínim congelat no es compleix; OOS 2024 continua
segellat i no s'ha d'obrir fins tenir mostra admissible.

## Regla per a la següent sessió

No repetir aquestes famílies ni ajustar els seus llindars. El següent carril
ha de ser una generació SQ nova amb train/validació separats, pressupost
d'intents, watchdog i família/mecanisme diferents. Cap resultat d'aquesta
campanya autoritza paper o live.
