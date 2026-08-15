# JPM Momentum 60 a final de mes

## Contracte executable

- Actiu: JPMorgan Chase (`JPM`), recurs SQ aïllat `JPM_MOM60_V1_D1`.
- Timeframe: D1, Dukascopy RTH NYSE 09:30–16:00, 390 minuts exactes.
- Només long i una posició simultània.
- Senyal a canvi de mes: `DayOfMonth[0] < DayOfMonth[1]`.
- Filtre: `Close[1] > Close[61]` (momentum positiu de 60 sessions).
- Entrada a mercat a l'open de la sessió nova; sortida a l'open després de 20
  barres. Es permet tancar i reobrir al mateix open.
- Sense volum, SMA, stop, target, trailing ni sortida EOD.

No s'ha ajustat cap paràmetre per JPM: és la transferència exacta de la regla
Momentum60 congelada abans d'obrir 2025–2026.

## Reconstrucció en SQ

1. Importar `JPMUSUSD_CANONICAL_D1_through_2026.csv` amb timezone
   `America/New_York`, timeframe D1, `pointValue=1`, tick 0,001 i mida/pas d'una
   acció. L'auditoria round-trip exigeix 2.401 dates i OHLC exactes.
2. Executar `build_aapl_momentum60_sqx_v1.py` amb
   `--strategy-name JPM_MOMENTUM60_MONTH_END_V1`; el nom històric del constructor
   es conserva per compatibilitat, però ara és reutilitzable.
3. Retest: `ExitAtEndOfDay=false`, `LimitTimeRange=false`,
   `ExitAtEndOfRange=false`, `MaxTradesPerDay=1`, fixed size 1 per provar la
   semàntica. Aplicar després accions senceres i costos IBKR.

## Evidència

- OOS natiu SQ 2024: 11 trades. A 500 $ stress: +19,39%, PF 2,409, win rate
  72,7% i DD 5,27%; a 1.000 $ stress: +27,54%, PF 2,689 i DD 6,03%.
- Confirmació posterior preregistrada 2025-01-01→2026-08-13: 11 trades. A
  500 $ stress: +22,15%, PF 2,586 i DD 7,57%; a 1.000 $: +23,80%, PF 2,544 i
  DD 8,91%.
- Diagnòstic de cartera 2022–2024: JPM +36,13%, PF 1,985 i DD 13,61%.
  CAT+MSFT+JPM: +22,72% sobre tres mànigues iguals, PF 1,369 i DD 10,68%.
  Correlacions mensuals JPM–CAT −0,0057 i JPM–MSFT 0,0007.
- Evidència a `data/ibkr_sq_v2/jpm_momentum60_v1/`.

## Limitacions i estat

La confirmació recent només té 11 trades i ja no és un segon holdout independent
després de la primera obertura en Python. El diagnòstic 2022–2024 és històric,
no un holdout nou. La concentració dels tres millors guanys i el drawdown
intratrade encara s'han de vigilar.

Classificació: `ADMITTED_RESEARCH_EDGE_AND_INCREMENTAL_PORTFOLIO_COMPONENT`.
És la tercera peça teòrica CAT+MSFT+JPM; paper i LIVE continuen no autoritzats.
