# SPY D1 short-reversal families

Rebutjades dues famílies sobre Dukascopy RTH D1 2017–2023, sense obrir l'OOS
2024 i sense executar SQCLI:

1. `spy-d1-shock-reversal-v1`: long després de xocs d'1/3 dies, només sobre
   SMA200 ascendent, holds 1/3/5. Només `1D -2%, hold 5` fou estable en train;
   validació 2022–2023 va tenir un únic trade i cap variant va passar.
2. `spy-symmetric-extreme-reversal-v1`: reversió long/short/both després de
   moviments absoluts d'1–2,5%, holds 1/3/5. Zero regions estables.

Font: 2.737.440 M1 únics, 1.901 sessions de 390 minuts, zero duplicats.
Evidència a `data/ibkr_sq_v2/spy_d1_shock_reversal_v1/`. Amb 500–1.000 USD,
la rotació i el mínim per ordre erosionen massa l'edge. No ampliar llindars post
hoc ni obrir 2024 per rescatar la família. Paper i LIVE no autoritzats.
