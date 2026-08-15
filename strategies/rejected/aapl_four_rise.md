# AAPL Four-rise — rebutjada

- Candidata congelada: `MSFT014_B4_SL1.4_PT4.4` transferida a AAPL.
- Entrada: quatre tancaments D1 consecutius no decreixents.
- Stop: 1,4%.
- Target: `4,4 × ATR(20)`.
- Holdout verge: 2025-01-01 a 2026-08-13.

## Resultat que causa el rebuig

24 operacions. Amb 1.000 $ i costos stress: −4,80%, PF 0,878 i DD 13,95%.
Amb 500 $: −10,63%, PF 0,718. Va fallar els gates preregistrats de retorn
positiu i PF mínim 1,05.

Evidència canònica:
`data/ibkr_sq_v2/aapl_four_rise_v1/final_decision.json`.

No optimitzar sobre aquest holdout ni reutilitzar la candidata amb paràmetres
veïns. Qualsevol nova hipòtesi AAPL ha de ser independent.

