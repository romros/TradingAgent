# Biblioteca d'estratègies verificades

L'objectiu és descobrir i conservar *edges* reproduïbles abans de decidir com
explotar-los. Una entrada no implica paper ni live. Cada estratègia avança per:

`idea → train → validació → veïnat → OOS → robustesa → holdout → executable`

Estat del nou objectiu buy-and-hold: [BUY_HOLD_OBJECTIVE_STATUS.md](BUY_HOLD_OBJECTIVE_STATUS.md).
La cartera teòrica CAT/MSFT/JPM/SGLN/NFLX supera el gate marginal 2022–2024.
NFLX s'admet només amb notional màxim de 1.000 USD: eleva el resultat stress
de +56,04% a +89,73%, amb CAGR 23,81% i DD 19,29%. El gate original de NFLX
a exposició completa continua fallat; aquesta admissió capada no l'esborra.

## CAT D1 — descens de pressió venedora (`Strategy 0.168`)

Estat: **reserva de recerca robusta; holdout 2025 intacte**.

- Mecanisme: entrada long quan `-DI(40)` gira a la baixa; interpreta una
  disminució de la pressió venedora, no una predicció per calendari.
- Entrada: market a l'open D1.
- Sortida: profit target `2,1 × ATR(30)` i stop `2,5 × ATR(30)`.
- Train: 2017-05-11–2021-12-30.
- Validació: 2022–2023, 36 trades, estrès IBKR +20,91%, PF 1,232 i DD 17,69%.
- OOS: 2024, 21 trades, estrès IBKR +13,23%, PF 1,333 i DD 15,81%.
- Veïnat: 79/81 punts passen train i validació amb costos d'estrès.
- Paritat: Python reprodueix 36/36 trades de validació, 21/21 OOS i 127/127
  pre-holdout, inclosos gap-reentry i prioritat stop intrabar.
- Robustesa nativa: l'execució canònica reporta 2.000 simulacions. SQ build 143
  persisteix 1.980 blobs i omet una cua de 20, que es penalitzen com a fallades:
  límit inferior rendible 99% contra el llindar congelat del 90%. El percentil
  100 conserva benefici +178,13, Ret/DD 2,53 i R-expectancy +0,1093.
- Limitació: el bootstrap IID de només 36 trades de validació té percentil 5
  negatiu. A més, els blobs `SimulationOrders.bin` no són llistes d'ordres
  autònomes exportables; la decisió utilitza la taula `SQStats` nativa i deixa
  explícita la incidència de persistència. No equival a disposar de 2.000
  traces d'operacions auditables.
- Capital: el resultat auditat pressuposa 1.000 USD, accions senceres, tot el
  capital realitzat disponible i sense marge. En estrès, 2017–2024 acaba en
  1.889,56 USD (+88,96%), PF 1,221 i DD 29,11%. Encara no és una recomanació.
- Bloqueig de release: el protocol congelat exigeix 60 trades OOS i només n'hi
  ha 21. El càlcul de capital complet tampoc prova encara el límit congelat de
  risc de l'1,5% per trade. Per això no s'obre el holdout malgrat que la
  robustesa de paràmetres sigui bona.

Evidència principal:

- `data/ibkr_sq_v2/cat_d1_trend_pilot/validation/audit_0_168.json`
- `data/ibkr_sq_v2/cat_d1_trend_pilot/validation/neighborhood_0_168.json`
- `data/ibkr_sq_v2/cat_d1_trend_pilot/oos/audit_0_168.json`
- `data/ibkr_sq_v2/cat_d1_trend_pilot/oos/parity_0_168.json`
- `data/ibkr_sq_v2/cat_d1_trend_pilot/pre_holdout/parity_0_168.json`

No s'ha accedit al holdout 2025. `paper_authorized=false` i
`live_authorized=false` fins completar robustesa, holdout i contracte IBKR.

### Cartera shadow de dos edges: SXR8 + CAT

Estat: **dues estratègies amb edge de recerca; només SXR8 està preparada per
shadow operatiu**. CAT no queda autoritzada per paper ni live.

- Assignació auditada: dues butxaques independents de 1.000 unitats, 50/50,
  sense leverage ni transferència de capital.
- Període comú 2019–2024, costos d'estrès: cartera +46,32%, PF 1,266 i
  drawdown de capital tancat 14,52%. CAT sola tenia 28,22% de drawdown.
- Prova estricta només validació+OOS 2022–2024: SXR8 +4,91%, CAT +28,52%,
  cartera +16,72%, PF 1,203 i drawdown 9,76%.
- Correlació mensual 2022–2024: 0,321, comptant zero quan una estratègia no
  opera. Per tant CAT aporta diversificació observable i no és una còpia del
  canvi de mes.
- Limitacions: drawdown calculat sobre operacions tancades, divises EUR/USD
  sense conversió i només 21 trades CAT en OOS 2024 versus el gate congelat
  de 60. El resultat és una cartera de recerca/shadow, no una promesa ni una
  autorització d'ordres.

Evidència reproduïble:

- `lab/sq_bridge/two_strategy_portfolio_v1.py`
- `data/ibkr_sq_v2/two_strategy_portfolio/sxr8_cat_v1.json`

Runner forward shadow CAT:

```bash
python3 apps/cat_0168_shadow_daily.py \
  --candles data/forward/CAT_CANONICAL_D1.csv \
  --session YYYY-MM-DD \
  --capital 1000
```

El CSV forward ha de contenir `date,open,high,low,close`, sessions úniques i
OHLC canònic (`high >= open/close`, `low <= open/close`). El runner falla
tancat davant candles incompletes o envelopes impossibles. Registra únicament
intents `HYPOTHETICAL_NOT_SENT` a `data/shadow/cat_0168.json`, conserva stop i
target congelats, aplica prioritat pessimista al stop i permet reentrada el
mateix open només després d'una sortida per gap, igual que SQ. No té cap client
de broker ni cap camí d'enviament d'ordres.

Pipeline diària recomanada, després del tancament NYSE:

```bash
python3 apps/cat_shadow_pipeline.py --capital 1000
```

La pipeline usa un lock no bloquejant, actualitza el feed, verifica que el SHA
coincideix amb el rebut, rebutja dades futures o de més de cinc dies, exigeix
45 sessions de warm-up i executa exactament una sessió. Estat llegible pel
panell: `data/shadow/cat_0168_pipeline_status.json`. Per diagnosi offline es
pot usar `--skip-fetch`; no s'ha d'utilitzar diàriament perquè podria amagar un
feed que no s'ha actualitzat.

El 2025+ històric no s'ha llegit ni utilitzat. El context corporatiu públic de
2026 només s'utilitza com a veto d'obsolescència, mai per ajustar paràmetres:
Caterpillar continua reportant activitat operativa i cotitzant com a equity
líquida, però això no valida l'edge futur.

## Tercera candidata — MSFT `capitulation_d1`

Estat: **tercer edge de recerca; pendent d'integrar al shadow IBKR**.

- Regla congelada: després d'una sessió amb cos inferior a −2% i close sota la
  banda Bollinger inferior 20/2, compra a l'open següent i ven al close del
  mateix dia.
- Auditoria ampliada amb 30 bps: MSFT 74 trades, PF 2,48, EV +76,3 bps i DD
  7,23%. P empíric contra entrades aleatòries aparellades per any: 0,0002;
  bootstrap 95% de l'EV: +36 a +155 bps.
- Persistència: 2014–2018 PF 5,88; 2019–2023 PF 6,10; monitoratge 2024–2026
  PF 2,52. NVDA confirma qualitativament la mateixa família.
- Auditoria IBKR sense leverage 2022–2024, butxaca de 1.000 USD i 30 bps:
  15 trades, +3,50%, PF 1,49 i DD tancat 3,54%.
- Correlació mensual màxima amb SXR8/CAT: 0,238.
- Cartera igualitària SXR8/CAT/MSFT 2022–2024: +12,31%, PF 1,215 i DD 6,79%.
  La cartera anterior de dos edges tenia +16,72% i DD 9,76%: MSFT redueix
  retorn mitjà perquè és poc freqüent, però aporta estabilitat.
- Diagnòstic 40/40/20: +13,90%, PF 1,208 i DD 8,02%. No es proven més pesos.

Limitació temporal: l'auditoria antiga ja va consultar 2024–2026 com a
monitoratge. Per tant no es presenta com un holdout verge. La nova auditoria de
cartera llegeix només fins a 2024 i no modifica la regla. `paper_authorized` i
`live_authorized` continuen falsos.

Evidència:

- `lab/out/alquimia/capitulation_anatomy_v1.json`
- `data/ibkr_sq_v2/three_strategy_portfolio/sxr8_cat_msft_v1.json`
- `lab/sq_bridge/three_strategy_portfolio_v1.py`

Round-trip natiu SQ completat: la regla congelada s'ha reconstruït com a SQX,
s'ha executat amb Retest supervisat sobre 2003–2024 i les **67 entrades de SQ
coincideixen exactament, data per data, amb les 67 de Python**. No hi ha senyals
absents ni extres. Els preus nominals no es comparen directament perquè la font
Python és ajustada i el recurs natiu SQ conserva OHLC nominals coherents amb
splits. Això valida la paritat de lògica, no autoritza paper ni live.

- `data/ibkr_sq_v2/msft_capitulation_native/retest/run/signal_parity_receipt_v1.json`
- `data/ibkr_sq_v2/msft_capitulation_native/retest/run/supervised_retest_receipt.json`
- `lab/sq_bridge/msft_capitulation_sq_parity_v1.py`

## Famílies addicionals rebutjades buscant el tercer edge

### Prima intradia aparent en CFDs Dukascopy — artefacte de font

L'efecte open→close 2022–2024 semblava extraordinari en AAPL/DE/JNJ/JPM/KO,
però la comparació diària amb Yahoo ajustat mostra un biaix sistemàtic de
mediana entre 7,8 i 38,3 bps/dia. KO passa de +22,76 bps/dia a Dukascopy a
-0,35 bps/dia a Yahoo; DE de +47,67 a +5,79. No és edge executable demostrat i
queda rebutjat abans d'SQCLI. Evidència:
`data/ibkr_sq_v2/overnight_premium/intraday_source_audit_v1.json`.

- Weekend effect en or físic SGLN/PHAU: l'edge brut es torna negatiu a OOS en
  totes tres execucions preregistrades; 70 bps setmanals l'enfonsen. Rebutjat.
- Momentum 12 mesos en Treasury UCITS IBTM/IDTL: IBTM falla validació d'estrès
  (−0,37%) i IDTL falla train i OOS. Rebutjat sense seleccionar venciment.
- Reversió de liquiditat de final de mes en bons: petita empremta bruta al
  principi, però IBTM gira negatiu a OOS, p combinades 0,36/0,43 i costos
  inviables. Rebutjada sense canviar finestres.

Artefactes: `data/ibkr_sq_v2/gold_weekend_effect/screen_v1.json`,
`data/ibkr_sq_v2/bond_ucits_tsmom/screen_v1.json` i
`data/ibkr_sq_v2/bond_month_end_reversal/screen_v1.json`.

## SPY D1 — canvi de mes (`last 1 + first 3`)

Estat: **edge estadístic defensable; candidat de recerca, no paper/live**.

- Regla congelada: comprar a l'open de l'última sessió del mes i vendre a
  l'open de la quarta sessió del mes següent. No usa cap indicador ni
  paràmetre ajustat al preu.
- Descobriment/transferència: va passar sobre SPX i, sense canviar la regla,
  sobre SPY ajustat per splits i dividends, instrument de referència operable
  a IBKR quan la classificació reguladora del compte ho permeti.
- Train 2017–2021: 59 trades, +30,22%, PF 1,889, DD 9,30%.
- Validació 2022–2023: 23 trades, +8,92%, PF 1,638, DD 5,57%.
- OOS 2024: 11 trades, +2,05%, PF 1,310, DD 7,25%.
- Validació + OOS: 34 trades, +11,16%, PF 1,526, Sharpe mensual 0,572.
- Mostra completa 2017–2024: t=1,957, p unilateral=0,0267. La mostra només
  fora de train no és significativa per si sola (p=0,171), per tant l'edge és
  moderat i no concloent.
- Robustesa congelada: 4/4 finestres veïnes positives tant en tota la mostra
  com el 2022–2024; 7/8 anys positius; bootstrap de 10.000 blocs anuals amb
  96,58% de mitjanes positives. El CI 95% encara inclou lleugerament zero.
- Cost IBKR tiered aproximat (0,35 USD mínim per ordre): a 200 USD, dues
  comissions més 2 bps de slippage eliminen l'edge (-1,97% el 2022–2024). A
  500 USD sobreviu (+5,29%); a 1.000 USD queda +7,82%. Són diagnòstics, no una
  promesa de rendiment.
- Limitacions: SPY pot estar restringit a clients retail de la UE si no hi ha
  KID PRIIPs aplicable; cal verificar el contracte concret del compte o
  transferir la regla a un UCITS S&P 500. Falten paritat amb dades IBKR,
  calendari oficial d'ordres, fiscalitat i paper trading.

Evidència principal:

- `data/ibkr_sq_v2/turn_of_month/screen_v1.json`
- `data/ibkr_sq_v2/turn_of_month/spy_transfer_v1.json`
- `data/ibkr_sq_v2/turn_of_month/robustness_v1.json`

El holdout 2025 continua segellat. `paper_authorized=false` i
`live_authorized=false`.

## Famílies rebutjades en el mateix embut

- Overnight long: rebutjada. El patró intradia enorme dels CFD Dukascopy és
  una característica de construcció de dades i no s'accepta com a edge IBKR.
- Connors RSI(2)/5/200: PF combinat 1,572 però t=1,418 i només 3 actius
  positius; no passa els criteris congelats.
- Turtle long 50/20: PF combinat 1,555 però t=1,192 i només 4/8 actius
  positius; no passa transferència.
- IBS diari clàssic, condicionat per SMA200 i executat de forma observable al
  següent open: rebutjat sense optimitzar. Amb 30 bps, validació+OOS suma 497
  trades sobre SPY/SXR8/CSPX/MSFT, zero actius positius i PF agregat 0,278.
  L'edge publicat depèn d'entrar al mateix close que genera el senyal o no
  sobreviu aquesta implementació; no es força amb llindars posteriors.
  Evidència: `data/ibkr_sq_v2/ibs_reversion/screen_v1.json`.
- Continuació de gap després de resultats: el comportament 2022–2024 és
  prometedor (17 trades, PF 2,64, t=1,33), però incompleix el mínim congelat
  de 20 trades i el train té PF 1,02, compost −2,97% i DD 22,65%. Queda com a
  lead rebutjat, no com a edge. Fitxa completa:
  `strategies/rejected/earnings_gap_continuation_v1.md`.

## SXR8/CSPX D1 — transferència UCITS del canvi de mes

Estat: **candidat UCITS prometedor; contracte IBKR del compte no verificat**.

- Fons: iShares Core S&P 500 UCITS ETF USD Acc, ISIN `IE00B5BMR087`.
- Regla: exactament la mateixa `last 1 + first 3` descoberta sobre SPX/SPY;
  no s'ha optimitzat.
- SXR8 (Deutsche Börse, EUR), validació 2019–2022 + OOS 2023–2024:
  70 trades, +56,52% brut, PF 2,335, DD 7,07%.
- SXR8 amb 1.000 EUR, mínim 1,25 EUR per ordre i 10 bps round-trip:
  +22,64%, PF 1,498 i DD 8,79%.
- CSPX (LSE, USD), mateix període: 70 trades, +36,38% brut, PF 1,695,
  DD 6,89%; amb el mateix estrès de costos: +6,81%, PF 1,146.
- Les dues cotitzacions passen individualment validació i OOS. El gate conjunt
  congelat falla perquè la correlació per data de sortida és 0,8981 contra
  0,95. Festius, EUR/USD i hores d'obertura diferents fan que no siguin
  rèpliques operatives exactes.
- Advertiment: 2012–2018 és feble en totes dues cotitzacions (SXR8 PF 1,111;
  CSPX PF 0,954). L'edge recent és clar, però pot ser dependent del règim.
- VUAA.MI també es va provar. La regla intacta falla el gate per 2024 pla;
  una optimització preregistrada només amb 2019–2021 va seleccionar sortida al
  cinquè dia, però va perdre el 2024 després de costos. Queda rebutjada.

Evidència:

- `data/ibkr_sq_v2/turn_of_month/cspx_transfer_v1.json`
- `data/ibkr_sq_v2/turn_of_month/ucits_transfer_v2.json`
- `data/ibkr_sq_v2/turn_of_month/ucits_optimization_v1.json`

No s'ha accedit a 2025+. Abans de paper cal confirmar `conid`, exchange,
permisos, fraccions i comissió real de SXR8 al compte IBKR objectiu.

Implementació read-only preparada:

- `packages/brokerage/ibkr_readonly.py`: allowlist de tres GET del Client
  Portal Gateway; no exposa cap endpoint d'ordres.
- `lab/sq_bridge/ibkr_sxr8_contract_probe.py`: cerca SXR8 i captura contractes,
  però actualment informa `BLOCKED_GATEWAY_UNAVAILABLE` perquè no hi ha Gateway
  autenticat a `https://localhost:5000`.
- `packages/strategy/turn_of_month.py`: calendari pur i determinista, basat en
  sessions reals de borsa i amb claus idempotents BUY/SELL per cicle mensual.
- `data/ibkr_sq_v2/turn_of_month/sxr8_calendar_plan_2012_2024.json`: 310
  accions històriques reproduïbles; no autoritza ordres.
- Contracte públic IBKR verificat: `conid=75776072`, SXR8, ISIN
  `IE00B5BMR087`, ETF en EUR, exchange `IBIS2`, horari publicat 09:00–17:45.
  Evidència local: `lab/sq_bridge/ibkr_sxr8_public_contract_v1.json`.
- Gate agregat: `data/ibkr_sq_v2/turn_of_month/sxr8_paper_readiness.json`.
  Avui és `PAPER_BLOCKED` exclusivament perquè falta autenticar el compte
  Gateway, confirmar que retorna el mateix conid, observar la comissió del
  compte i validar sizing d'accions senceres o fraccionades.
- Sense compte, el gate separat és `SHADOW_PAPER_READY`: calendari oficial
  Xetra 2026, sizing d'accions senceres, ledger atòmic/idempotent i zero
  capacitat d'enviar ordres. Proper cicle previst: 31-08-2026 / 04-09-2026.

## Gap intradia UCITS — rebutjat

- Hipòtesi inicial preregistrada: comprar gaps inferiors a −1% a l'open i
  sortir al close. Falla fortament sobre SXR8 i CSPX en train, validació i OOS.
- La inversió short semblava prometedora en aquestes dues sèries, però era una
  observació posterior al test. Es va preregistrar una confirmació independent
  sobre VUAA.MI abans d'accedir al seu rendiment de gaps.
- Confirmació VUAA després de costos: desenvolupament −20,36%, validació
  −13,34%, OOS 2024 −2,65%; PF combinat 0,448. El patró no transfereix i es
  rebutja en ambdues direccions.
- Evidència: `data/ibkr_sq_v2/ucits_gap_fade/screen_v1.json` i
  `data/ibkr_sq_v2/ucits_gap_continuation/confirmation_v1.json`.

## Momentum 12 mesos en ETC d'or físic — rebutjat

- Vehicles amb KID/producte físic: iShares Physical Gold ETC (`SGLN.L`, ISIN
  `IE00B4ND3602`) i WisdomTree Physical Gold (`PHAU.L`, ISIN
  `JE00B1VS3770`). 2025+ segellat.
- Regla congelada: revisió mensual, long si el close mensual supera el de fa
  dotze mesos; altrament cash. Cost per canvi de posició per 1.000 EUR.
- El 2019–2024 és positiu: SGLN +78,84%, Sharpe 0,875; PHAU +50,65%, Sharpe
  0,616. Però el train 2012–2018 és negatiu en tots dos (−17,46% i −20,40%).
- PHAU supera el drawdown congelat (25,74% > 20%) i la correlació de retorns
  mensuals és només 0,701. No és transferible ni estable entre règims.
- Decisió: rebutjar sense optimitzar. Evidència:
  `data/ibkr_sq_v2/gold_etc_tsmom/screen_v2.json`.
