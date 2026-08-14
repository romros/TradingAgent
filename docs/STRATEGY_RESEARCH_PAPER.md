# Registre mestre de recerca d'estratègies

Data de tall: 2026-08-14. Aquest document és l'índex humà; els JSON i SQX
enllaçats són l'evidència reproduïble. «Edge» significa evidència històrica
defensable, no una promesa de rendiment ni autorització de paper/live.

## Estat executiu

| Classe | Estratègia | Actiu | Mecanisme | Decisió |
|---|---|---|---|---|
| Admesa | CAT 0.168 | CAT | trend/pullback D1 | Edge de recerca; validació i OOS positius, asset-specific |
| Admesa | capitulation_d1 | MSFT | reversió després de xoc | Edge de recerca; paritat exacta de senyals SQ/Python |
| Condicional | last-1 + first-3 | SXR8 | fluxos de canvi de mes | Positiva amb 1.000 EUR, però dependent de règim i contracte UCITS pendent |
| Watchlist | JPM 0.24 | JPM | trend/reversion D1 | +17,64% stress a validació, però només 24 trades |
| Rebutjada | AAPL 4.1.174 | AAPL | ROC reversion H1 | OOS stress −17,19%, PF 0,731 |
| Rebutjada | JNJ defensive v1 | JNJ | trend/pullback D1 | 0/8 candidats passen validació; OOS 2024 no obert |
| Overlay, no edge autònom | volatility-managed v1 | SPY | exposició inversa a volatilitat | Millora Sharpe/DD en validació, però falla 2/2 anys positius; OOS segellat |

La llibreria encara no està preparada: hi ha dos mecanismes admesos, un de
condicional i en calen almenys quatre d'independents abans de formar una
cartera teòrica final.

## Registre «no repetir»

No s'ha de repetir una fila amb els mateixos actius, senyal, execució i
períodes. Només es pot reobrir si hi ha una hipòtesi materialment nova,
millors dades o una correcció demostrada d'un error metodològic.

| Família falsada | Motiu principal | Evidència |
|---|---|---|
| JNJ D1 defensive trend/pullback | Quatre candidats negatius amb costos i quatre amb sortida same-bar D1 ambigua | `data/ibkr_sq_v2/jnj_d1_defensive_pilot/validation_summary_v1.json` |
| AAPL H1 ROC 4.1.174 | OOS negatiu després de costos | `data/ibkr_sq_v2/aapl_h1_roc_reversion_genetic/oos/4_1_174/small_account_audit.json` |
| IBS D1 observable next-open | 497 trades, zero actius positius, PF agregat 0,278 | `data/ibkr_sq_v2/ibs_reversion/screen_v1.json` |
| RSI2 clàssic en índexs | Validació negativa en SPY/SXR8/CSPX | `data/ibkr_sq_v2/index_rsi2/screen_v1.json` |
| Donchian 55/20 en accions | PF pooled de validació 0,797; només 3/9 sleeves positius | `data/ibkr_sq_v2/equity_donchian/screen_v1.json` |
| KO–PEP pairs | Validació −13,55%, PF 0,057 | `data/ibkr_sq_v2/ko_pep_pairs/screen_v1.json` |
| CAT 0.168 transferida a DE/UNP/CMI | L'edge no es transfereix; OOS/costos fallen | `data/ibkr_sq_v2/cat_d1_trend_pilot/transfer/` |
| Prima intradia Dukascopy US equities | Artefacte de construcció de dades contra fonts ajustades | `data/ibkr_sq_v2/overnight_premium/intraday_source_audit_v1.json` |
| Weekend gold ETC | OOS/costos negatius | `data/ibkr_sq_v2/gold_weekend_effect/screen_v1.json` |
| Momentum i reversió de final de mes en bons UCITS | Validació/OOS o costos fallen | `data/ibkr_sq_v2/bond_ucits_tsmom/screen_v1.json`, `data/ibkr_sq_v2/bond_month_end_reversal/screen_v1.json` |
| 52-week-high en cinc large caps supervivents | Validació 2022–2023 negativa; l'OOS 2024 bo no rescata el gate | `data/ibkr_sq_v2/equity_momentum_portfolio/screen_v1.json` |
| Turnaround Tuesday SPY, entrada observable next-open | Train −16,00%; validació −21,42%, PF 0,390 i 0/2 anys positius | `data/ibkr_sq_v2/turnaround_tuesday/screen_v1.json` |
| SPY volatility-managed 10%/21d mensual com a estratègia autònoma | Millora Sharpe i DD, però 2022 continua negatiu i falla el gate de 2/2 anys; conservar només com a overlay de risc | `data/ibkr_sq_v2/spy_volatility_managed/screen_v1.json` |
| Dual momentum mensual SPY/PHAU/IDTL, formació 12 mesos | Validació −28,08%, PF 0,247, DD 30,49% i 0/2 anys positius | `data/ibkr_sq_v2/multi_asset_dual_momentum/screen_v1.json` |
| Recuperació intradia de gaps SPY ≤−1% | Validació −7,27%, PF 0,735 després de 30 bps; no invertir el signe post hoc | `data/ibkr_sq_v2/spy_gap_down_recovery/screen_v1.json` |

## Fonts GitHub revisades

Cap repositori es considera prova d'un edge. Es classifiquen així:

- `QuantConnect/Lean`: motor madur i exemples multi-actiu. Útil per contrastar
  semàntica de futurs, fees i fills; els exemples no són resultats promocionables.
- `kernc/backtesting.py` i `pmorissette/bt`: motors reutilitzables. Són útils
  com a oracle independent, no com a catàleg d'estratègies rendibles.
- `s-kust/python-backtesting-template`: workflow interessant perquè separa
  anàlisi estadística del senyal, backtest i optimització. És una idea
  metodològica compatible amb el nostre embut.
- `trustdan/trend-following-backtesting-strategies`: catàleg de moltes variants
  i una observació útil —el resultat depèn més de l'actiu que de la complexitat—,
  però les xifres són autoreportades i s'han de reproduir amb les nostres dades.
- `DaruFinance/quant-research-framework`: idees de walk-forward, règims,
  invariants anti-look-ahead i paritat entre motors. És recent i s'ha d'auditar
  abans de reutilitzar codi.

Política d'importació: primer extreure una hipòtesi simple; després
preregistrar-la; reproduir-la amb dades canòniques; aplicar costos, validació,
OOS i robustesa. Mai importar el retorn anunciat pel repositori com a evidència.

## Fonts canòniques locals

- Catàleg verificable: `lab/sq_bridge/theoretical_strategy_library_v1.json`
- Estat computat: `data/ibkr_sq_v2/strategy_library/status_v1.json`
- Explicació extensa i arquitectura: `docs/STRATEGY_LIBRARY.md`
- Evidència de cada campanya: `data/ibkr_sq_v2/<campaign>/`

`paper_authorized=false` i `live_authorized=false` per a tota la llibreria.
