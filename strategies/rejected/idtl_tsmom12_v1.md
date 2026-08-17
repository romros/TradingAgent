# IDTL durada TSMOM12 — rebutjada

Hipòtesi nova respecte del dual momentum rebutjat: operar només el règim de
tendència de bons del Tresor americà de llarga durada, long o cash, amb la
mateixa regla mensual de 12 mesos ja validada conceptualment sobre or.

Amb 3 GBP per canvi de posició i 10 bps de slippage:

- train 2016–2021: +4,91%, Sharpe 0,127 i DD 21,62%;
- validation 2022–2023: −6,50%;
- OOS 2024: −4,47%;
- combinat 2022–2024: −10,68%, Sharpe −0,738.

Només queda invertida cinc mesos dels 35 recents. No proporciona retorn ni una
defensa útil i no passa cap reinterpretació de cartera. Decisió:
`REJECT_IDTL_TSMOM12`.

Evidència: `data/ibkr_sq_v2/idtl_tsmom12_v1/screen.json`.
