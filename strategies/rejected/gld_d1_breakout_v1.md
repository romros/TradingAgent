# GLD D1 breakout v1

Nou màxim de tancaments de 60/120/200 sessions, entrada al següent open;
sortida després de nou mínim de 20/60/120 sessions. Nou variants, long-only,
accions senceres i costos IBKR stress.

Tres variants veïnes van passar train 2017–2021 i validació 2022–2023. Abans
d'obrir 2024 es va congelar `GLD_BREAKOUT_E120_X60`. L'OOS 2024 no conté cap
trade complet: la posició queda censurada perquè no arriba la sortida dins del
període. Decisió `REJECT_OOS`; no s'ha valorat a mercat ni canviat la sortida.

Font: 2.767.680 M1 únics, 1.922 sessions RTH de 390 minuts. Evidència a
`data/ibkr_sq_v2/gld_d1_breakout_v1/`. SQCLI, paper i LIVE no autoritzats.
