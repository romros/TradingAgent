# JNJ/KO/PEP — reversió després de xoc 2 ATR rebutjada

Regla única preregistrada: en tendència sobre SMA200, una caiguda diària
d'almenys 2 ATR20 activa compra al següent open i sortida tres sessions més
tard. Accions senceres, 1 USD per ordre i 10 bps adversos per costat.

Falla desenvolupament per densitat i persistència. Train: 9 trades, −2,11% i
PF 0,821. Validació: +1,26% i PF 1,353, però només quatre trades i només dos
actius positius. No s'obre OOS 2024 ni es redueix retrospectivament el llindar
del xoc.

Evidència: `data/ibkr_sq_v2/defensive_equity_atr_shock_v1/development.json`.
