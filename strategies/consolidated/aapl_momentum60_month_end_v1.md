# AAPL Momentum 60 a final de mes

## Contracte executable

- Actiu: Apple (`AAPL`), recurs SQ `AAPL_IBKR_V4_D1`.
- Timeframe: D1, font Dukascopy RTH NYSE/Nasdaq ajustada pel split 4:1 de 2020.
- Direcció: només long; una posició simultània.
- A l'open d'una nova sessió, detectar canvi de mes amb
  `DayOfMonth[0] < DayOfMonth[1]`.
- Exigir momentum positiu: `Close[1] > Close[61]`, equivalent a comparar
  l'últim tancament complet amb el de 60 sessions abans.
- Entrada: mercat al mateix open que confirma el canvi de mes.
- Sortida: open després de 20 barres (`ExitAfterBars=20`). SQ pot tancar i
  reobrir al mateix open; aquesta igualtat és part de la semàntica certificada.
- Sense SMA, stop-loss, target, trailing, break-even ni sortida EOD.
- Una posició `EndTest` que no completa 20 barres és right-censored i no entra
  en les mètriques.

## Reconstrucció en StrategyQuant

El constructor determinista és
`lab/sq_bridge/build_aapl_momentum60_sqx_v1.py`.

1. Importar `AAPLUSUSD_CANONICAL_D1_through_2026.csv` com
   `AAPL_IBKR_V4_D1`, zona `America/New_York`, `pointValue=1`, mida mínima i
   pas d'una acció, spread zero.
2. Executar el constructor amb un template D1 compatible. El constructor
   substitueix la regla, elimina SL/PT i resultats heretats i fixa 20 barres.
3. Generar un Retest D1 amb `ExitAtEndOfDay=false`, `LimitTimeRange=false`,
   `ExitAtEndOfRange=false` i `MaxTradesPerDay=1`.
4. Exportar ordres. Per 2025-01-01..2026-08-13 han d'existir exactament 10
   entrades completades coincidents amb Python; la posició 2026-08-03 és
   `EndTest` incompleta i s'exclou.
5. Auditar amb accions senceres i els plans IBKR tiered/fixed/stress fora d'SQ.

## Evidència

- Holdout recent: 2025-01-01..2026-08-13, 10 trades completats.
- 500 $ stress: +37,89%, PF 3,013, win rate 70%, DD 8,89%.
- 1.000 $ stress: +39,89%, PF 3,189, DD 8,64%.
- Paritat exacta: `data/ibkr_sq_v2/aapl_momentum60_v1/native_holdout/signal_parity.json`.
- Costos: `data/ibkr_sq_v2/aapl_momentum60_v1/native_holdout/ibkr_cost_audit.json`.
- Robustesa: 10.000 bootstraps; 95,81% positius, percentil 5 de retorn +2,11%,
  leave-one-out 100% positiu, a `data/ibkr_sq_v2/aapl_momentum60_v1/robustness.json`.

## Limitacions

Deu operacions continuen sent una mostra petita. El bootstrap IID no representa
clustering de règims. L'anàlisi d'aportació incremental i solapament amb CAT i
MSFT encara és pendent. Admesa per recerca; paper i LIVE no autoritzats.

