# Alquímia — laboratori quantitatiu SQ → Ostium

**Data:** 2026-08-02
**Estat:** MVP en construcció; validació XAU H4 executada
**Capital canònic:** 200 USDC

Perfil i guardrails de l'operador:
[`OPERATOR_PROFILE_AND_RISK_POLICY.md`](OPERATOR_PROFILE_AND_RISK_POLICY.md).

## Missió

Alquímia és el laboratori determinista per descobrir, falsar i industrialitzar
estratègies executables directament a Ostium. StrategyQuant genera candidats;
MT4 és només un format d'exportació; el runtime final és Python amb TradingAgent
(decisió/risc) i BrokerageService (dades/execució).

Objectiu: 3–6 estratègies robustes i complementàries per a un petit inversor.

## Pipeline canònic

```text
Mercat Ostium executable
 → timeframe/dataset certificats
 → generació evolutiva SQ
 → IS → OOS → Monte Carlo/estrès → walk-forward
 → tuning controlat → holdout final congelat
 → exportació SQ/MT4/pseudocodi → traducció Python
 → paritat SQ↔Python → paritat SQ↔BS↔Ostium
 → simulació 200 USDC → paper Ostium
 → live només amb evidència i autorització explícita
```

TRAIN cerca estructures; VALIDATION selecciona; OOS/walk-forward comprova
estabilitat; FINAL HOLDOUT no s'utilitza mai per ajustar. Si falla el holdout,
es rebutja o es formula una hipòtesi nova. Cada campanya registra configuració,
rangs, versions, datasets, seed quan SQ l'exposi i hashes.

## Gate Ostium abans de gastar CPU

Cal confirmar: perpetual actual, pair/pair ID, símbols SQ i BS, històric comparable,
oracle, horari, fees, rollover, leverage, mínims compatibles amb 200 USDC i paritat
certificable. `research_eligible` permet investigar; `live_eligible` exigeix PASS
del registre BS. Allowlist: [`lab/sq_bridge/ostium_markets.json`](../lab/sq_bridge/ostium_markets.json).

Ostium ofereix perpetuals sintètics liquidats en USDC, no tokens spot custodiats.

## Robustesa

- Monte Carlo/bootstraps i ordre de trades.
- Spread, slippage, retard, costos base/conservadors/estrès.
- Pertorbació de paràmetres i candles.
- Walk-forward i règims de mercat.
- MAE, gaps, liquidació i leverage.
- Correlació/exposició de cartera.
- Fonts, timezone, sessions i construcció de candles.

Un PASS de SQ només autoritza verificació independent.

## SQ/MT4 → Python

`.sqx` és propietari: no pressuposem traducció universal. Limitarem SQ a blocs
suportats; qualsevol regla no reproduïble queda `UNSUPPORTED`. Python ha de
reproduir senyals, timestamps, entries/exits, stops/targets, trades i PnL dins
toleràncies. Després es recalcula amb bid/ask, impact, gas, fees i rollover Ostium.

## Compte petit: 200 USDC

SQ pot usar 10.000 USD com a escala tècnica, però Alquímia resimula
100/200/300/500/1.000 USDC i decideix sobre 200.

```text
risk_budget = equity × risk_per_trade
notional = risk_budget / adverse_move_or_stop_pct
required_leverage = notional / collateral
approved_leverage = min(required_leverage, venue_max, BS_guard_max,
                        stress_safe_max, portfolio_risk_max)
```

Inclou mínims, collateral, bid/ask, impact, slippage, gas, fees, rollover, horari,
tancament diari, liquidació, drawdown i reserva. El leverage no crea edge: es tria
el més alt que encara supera els gates.

Verdictes: `SMALL_ACCOUNT_200_USDC_VIABLE`, `VIABLE_BUT_TOO_INFREQUENT`,
`NOT_VIABLE_COSTS`, `NOT_VIABLE_MIN_SIZE`, `NOT_VIABLE_LIQUIDATION` i
`NOT_VIABLE_WITH_200_USDC`.

## Pipelines, hooks i servei futur

Pipelines versionades: crear, iniciar, aturar, reprendre, observar, exportar i
arxivar. Configuracions manuals antigues són plantilles, mai execucions cegues.

```text
SQ stdout/API → parser local → status.json → hook de canvi/finalització
```

L'estat conté fase, generades/acceptades/rebutjades, errors, recursos, hashes i
artifacts. PinchTab/Playwright només si SQCLI no cobreix una configuració. Primer
CLI i artifacts; API/web només quan el pipeline complet funcioni. Recerca mai
autoritza live.

La política canònica per pressupost, estancament, checkpoints i recuperació és
[`SQ_CAMPAIGN_STOPPING_AND_HANDOFF.md`](SQ_CAMPAIGN_STOPPING_AND_HANDOFF.md).
El watchdog pilot existent encara no implementa tota aquesta política.

## MSFT: calendari i sessió

### Política de fonts

Dukascopy és la font històrica preferida quan l'actiu hi existeix, perquè les
campanyes anteriors han mostrat millor paritat de preu i hora amb Ostium que
Yahoo. Yahoo no s'ha de considerar automàticament executable a Ostium.

`MSFT`, `NVDA` i `NDXUSD` no estan disponibles a Dukascopy segons el contracte
actual de BrokerageService. Per aquests actius, Yahoo només pot actuar com a
font de recerca provisional i de referència per ajustos corporatius. Abans de
Builder cal certificar contra el tram natiu d'Ostium: escala de preus, retorns
D1, gaps, timestamp/sessió, splits i divergència OHLC. Si aquesta paritat no és
explicable o supera els llindars congelats, la família queda bloquejada encara
que el backtest Yahoo sigui positiu.

El recurs SQ i el mapping també han de coincidir explícitament: el recurs nou
és `MSFT`, el broker usa `MSFT` i Ostium executa `MSFTUSD`. El símbol SQ antic
`MSFTUSUSD_TICK_UTCMinus05` no es reutilitza sense demostrar-ne la procedència.

La recerca MSFT es divideix deliberadament en dues famílies independents:

- `MSFT D1 calendar`: dia de la setmana, dia/setmana del mes, primer o últim
  dia de negociació i direcció long/short. Long i short s'avaluen per separat;
  no s'imposa simetria ni es permet seleccionar el millor dia després de veure
  el holdout.
- `MSFT intraday session`: hora d'entrada, hora de sortida i franges de sessió.
  Aquesta família queda bloquejada fins a disposar d'un historial intradia llarg,
  amb timezone, DST, sessió regular i paritat amb `MSFTUSD` d'Ostium certificats.

La família de calendari ha de corregir explícitament per múltiples proves: cada
combinació dia/direcció compta com una hipòtesi intentada. A més dels gates
habituals, ha de superar validació temporal per anys, comparació amb entrada
aleatòria condicionada al mateix nombre d'operacions i costos del compte de
200 USDC. Els aproximadament cinc mesos de candles natives Ostium disponibles
el 2026 només serveixen per paritat recent, no per descobrir efectes horaris.

### Resultat MSFT D1 close v1 (2026-08-02)

La paritat recent certifica únicament el tancament D1: 95 dies solapats,
diferència mediana 5,28 bps, p95 24,65 bps i correlació de retorns 0,9975 entre
Yahoo sense ajustar i el tancament robust d'Ostium. Open/high/low i execució
intrabar continuen sense certificar.

SQ va generar 80 estratègies en quatre famílies (trend/calendar × long/short).
El front Pareto IS va congelar 48 candidats. El Retest SQCLI 143 queda encallat
després de preparar MSFT fins i tot amb un sol SQX; es va aturar netament i es
va activar el fallback Python auditable. El traductor reprodueix el subset
close/calendar, entrada next-open, stop percentual o ATR i target ATR, amb stop
primer quan una barra toca stop i target.

Validació + OOS van deixar 8 candidats quantitativament positius. Abans d'obrir
el holdout es van congelar tres finalistes compatibles amb close-only:

- `calendar long 0.14`: primer dia negociable del mes, stop 2,1%, target 3,9×ATR20.
  Holdout: 29 trades, PF brut 2,03, retorn 45,4%, DD 15,6%. Amb 36 bps: PF 1,66,
  retorn 31,1%.
- `calendar long 0.77`: primer dia de mes amb confirmació de tancament, stop
  2,8×ATR30 i target 4,1×ATR20. Holdout: només 12 trades; PF estrès 1,41.
- `trend long 0.14`: compra després de tres tancaments descendents, stop
  2,6×ATR30 i target 4,6×ATR25. El PF cau a 1,12 en holdout amb estrès.

El primer semblava el millor candidat de recerca, però la falsificació posterior
el rebutja com a **timing edge**. Amb 36 bps, 500 calendaris aleatoris que també
intenten una entrada per mes obtenen una mediana superior en validació (37,38%
contra 26,51%; p empírica 0,617). Tampoc és significatiu en OOS (p 0,295) ni en
holdout (p 0,186). Les 27 pertorbacions ±10% de stop/target sí que passen els
gates: els paràmetres són estables, però això no demostra que el primer dia de
mes aporti informació respecte a estar long MSFT en un dia mensual qualsevol.

El leverage preliminar de 21× tampoc supera la història completa: el llindar de
liquidació proxy és 4,76% i hi ha un gap de 4,94% durant validació, a més d'un
11,12% a train. El primer nivell de la graella sense gaps històrics més grans que
el llindar proxy és 8× (12,5%), encara sense certificar contra l'oracle d'Ostium.

Decisió final de la família: `REJECT_CALENDAR_TIMING_EDGE_KEEP_LONG_DRIFT_REFERENCE`.
No s'integra al paper bot i no es retoca després del holdout. Amb 200 USDC i risc
màxim de l'1%, el nocional teòric continuava limitat a ~81,30 USDC; el leverage
només canviava el marge, no aquest risc. Artifacts canònics: `msft_source_parity.json`,
`msft_finalists_holdout.json`, `msft_final_gate.json`,
`msft_calendar_014_robustness.json` i `msft_calendar_014_gap_risk.json`.

## Revisió de famílies famoses (2026-08-02)

S'han contrastat time-series momentum, volatility management, overnight equity,
opening-range breakout i reversió curta amb evidència publicada i amb les nostres
campanyes. Dos experiments nous usen exclusivament Dukascopy local:

- TSMOM EURUSD+XAUUSD: el lookback 126d és positiu brut en validació i OOS,
  però fins i tot el carry base conservador del 4% el torna negatiu. Holdout segellat.
- ORB XAU 08:20 NY: 15/30/60 minuts; totes perden abans de costos d'estrès.
  Millor OOS PF base 0,805 sobre 1.215 trades. Holdout segellat.

No hi ha nova candidata. `capitulation_d1` continua sent l'única família amb
evidència pròpia repetida i es manté només en paper. Revisió completa:
[`STRATEGY_EVIDENCE_REVIEW_2026.md`](STRATEGY_EVIDENCE_REVIEW_2026.md).

### Capitulació confirmada close-only v1

S'ha preregistrat una prova diferent del senyal productiu: caiguda diària
normalitzada per volatilitat, recuperació observable del 25% o 50%, entrada al
tancament de confirmació i sortida després d'1–3 dies. La graella conté 36
variants per actiu sobre MSFT, NVDA i QQQ; train 2004–2013, validació 2014–2018,
OOS 2019–2023 i holdout 2024–2026 segellat.

Cap actiu passa. MSFT falla validació (PF base 0,82; p contra timing aleatori
0,832), NVDA passa de PF 2,09 al train a 0,35/0,75 fora de train, i QQQ és
negatiu en els tres trams. Decisió:
`REJECT_HOLDOUT_REMAINS_SEALED`. No es tuneja, no passa a SQ i no modifica
`capitulation_d1`. Metodologia, runner i resultat:
`methodology_confirmed_capitulation_v1.json`,
`confirmed_capitulation_campaign.py` i
`confirmed_capitulation_v1_decision.json`.

### Anatomia del `capitulation_d1` congelat

L'auditoria preserva la regla productiva exacta: senyal al close de T, entrada
a l'open de T+1 i sortida al close de T+1. Amb 15 bps conservadors, MSFT dona
74 trades, PF 2,98 i EV +91,3 bps; NVDA 144, PF 1,82 i +70,4 bps; QQQ 83,
PF 2,00 i +49,5 bps. Els p empírics contra dies aleatoris aparellats per any
són 0,0002, 0,0004 i 0,0002. L'edge és intradia: el gap previ no explica el
retorn operat. QQQ és negatiu el 2003–2013 i continua sent només proxy.

La història ampliada invalida el cap global antic de 20x. La pitjor MAE
observada és 5,57% MSFT, 12,75% NVDA i 10,07% QQQ. A 20x, el proxy hauria
liquidat 2,70%, 7,64% i 2,41% dels trades. Amb buffer del 25%, els nous caps
de **paper** són MSFT 10x i NVDA/NDXUSD 5x; fallback 5x. El nocional continua
limitat independentment pel tram vigent del glidepath i marge màxim 35%. Cal certificar open/low
contra Ostium abans de considerar aquests caps per live.

El paper executor aplica aquesta separació de forma explícita a les noves
operacions: pressupost de risc segons capital, stop diagnòstic per actiu, nocional
`risc/stop` i collateral `nocional/leverage`. Si el low diari travessa el stop,
registra `stop_settled`. No hi havia trades pendents durant la migració i no
s'ha reescrit cap operació històrica.

Amb el stop aplicat i 200 USDC, MSFT conserva EV de +0,351 USDC/trade en
conservador i +0,288 en estrès; NVDA +0,212 i +0,169. QQQ baixa a +0,126 i
+0,069, respectivament. Per això el paper actiu per defecte queda en
`MSFT,NVDA`; NDXUSD continua watchlist fins que la paritat nativa i l'economia
d'estrès siguin suficients. Els costos per defecte nous són 8/15/30 bps.

#### Resultat combinat MSFT + NVDA amb 200 USDC

Les 218 operacions s'han ordenat cronològicament; senyals simultanis comparteixen
el capital inicial del dia i no fan compounding artificial entre ells. Període:
23,05 anys, aproximadament 9,46 trades/any.

| Cost | Guany amb risc fix 2 USDC | Capital final fix | Guany compounding 1% | Capital final | CAGR |
|---|---:|---:|---:|---:|---:|
| Base 8 bps | 61,54 | 261,54 | 71,14 | 271,14 | 1,33% |
| Conservador 15 bps | 56,49 | 256,49 | 64,39 | 264,39 | 1,22% |
| Estrès 30 bps | 45,65 | 245,65 | 50,47 | 250,47 | 0,98% |

Aquests són resultats històrics, no una projecció. El compounding és limitat
per la baixa freqüència i el risc 1%. L'antic 250→772 a 20x no és comparable:
assumia una exposició molt superior i zero liquidacions, hipòtesi invalidada
per la història ampliada.

#### Risk glidepath

El paper aplica risc decreixent per capital: <400 USDC 1,5%; 400–999 1,25%;
1.000–2.499 1%; 2.500–4.999 0,75%; ≥5.000 0,5%. El leverage no augmenta el
pressupost de risc; només redueix el collateral necessari dins els caps per
actiu.

Simulació cronològica MSFT+NVDA des de 200 USDC: base 314,91, conservador
303,23 i estrès 279,62. Drawdown màxim conservador 4,67%. En 23,05 anys cap
escenari arriba al primer llindar de 400 USDC; per tant, el glidepath és una
infraestructura correcta però no resol la baixa freqüència. Calen estratègies
independents addicionals, no més risc sobre el mateix edge.

### EURUSD intradia v2 — sessions DST

Pilot Dukascopy de 549.497 candles M15 (2004-01-01–2026-02-27), sessions
Europe/London i America/New_York amb DST. Es van congelar 10 variants
representatives de breakout del rang asiàtic, continuació d'expansió i reversió
d'expansió; long/short, entrada posterior al senyal, stop/target i tancament
intradia. Train 2004–2013, validació 2014–2018, OOS 2019–2023; holdout segellat.

Cap família s'apropa al gate fins i tot amb 8 bps: breakout PF 0,31/0,22 en
validació/OOS; continuació 0,11/0,06; reversió 0,07/0,06. Tenen 593–684 trades
OOS, de manera que no és falta de mostra. Decisió `REJECT_NO_SQCLI`: SQ no
optimitza una família sense edge brut/base. Runner ~49 s amb cache de sessions.

Artifacts: `methodology_eurusd_intraday_v2.json`, `eurusd_intraday_v2.py` i
`eurusd_intraday_v2_decision.json`.

Artifacts: `methodology_capitulation_anatomy_v1.json`,
`capitulation_anatomy.py` i `capitulation_anatomy_v1.json`.

## Campanya XAUUSD H4 (2026-08-02)

La incidència del Retest queda resolta: cal partir d'un projecte Retest **H4**
que SQ 143 ja hagi executat, conservar-ne el contracte i empeltar-hi només el
recurs XAU, símbol, dates i costos. El pilot nadiu va retestar `0.7893` en
0,83 s; no era un bloqueig del motor.

S'han validat els 8 representants estructurals de les 60 estratègies descobertes,
en el tram segellat 2015-02-07–2019-07-16, H4, slippage SQ 300 i risc 1%.
Resultat: **0/8 passen**. Els menys dolents són `0.106720` (PF 1,06), `0.34159`
(PF 1,05) i `0.7893` (PF 1,04), tots per sota del gate PF 1,15. `0.91375`
guanya 343,19 amb 41 trades però falla el filtre automàtic de mostra; la resta
inclou pèrdues o altres filtres automàtics. No s'ha obert el holdout.

Decisió: aquesta shortlist no avança a OOS, Monte Carlo, traducció Python ni
Ostium. Les 60 originals es conserven com a univers congelat/evidència de biaix
de selecció. Artifact canònic:
`lab/out/alquimia/xau_h4_native_shortlist_validation_inventory.json`.

### Nova família stop-channel breakout R2

Hipòtesi dirigida: ordres stop sobre màxim/mínim recent, sortides ATR i com a
màxim un filtre ADX/ATR/ROC. Random va generar 63 intents i va omplir 40 places;
10/40 van passar validació i 4/10 OOS. Amb slippage duplicat (800 unitats SQ),
`0.26`, `0.33` i `0.37` continuen passant. Els tres també passen Monte Carlo
exclusiu de paràmetres: 1.000 simulacions per candidat i 3.003 membres executats
verificats dins els SQX.

El gate posterior confirma que `0.37` és estable per anys (5/5 OOS positius),
no concentra el benefici i no simula liquidacions a 20x (MAE màxim 3,97%). Però
l'economia de 200 USDC falla: a risc 1% l'EV és 0,035 USDC base i 0,019 en estrès;
a risc 3% només passa base i falla conservador/estrès. El funding encara no s'ha
deduït i només ho empitjoraria.

Estat final de la família: `REJECT_FOR_200_USDC_KEEP_RESEARCH_REFERENCE`.
No s'obre holdout ni es consumeix feina de traducció/paritat. El holdout continua
intacte. Resum:
`lab/out/alquimia/xau_h4_stop_breakout_r2_gate_summary.json`.

### Compressió ATR + breakout R3

Nova hipòtesi posterior a R2: exigir ATR decreixent abans de l'entrada stop.
5/40 passen validació, 2/5 OOS i només `0.74` passa slippage 2×. Falla després:
2/5 anys OOS positius i, amb 200 USDC/risc 1%, PnL de +4,17 base i +0,29 estrès
en 130 trades. El cap preliminar arriba a 30x, però el nocional queda limitat pel
risc i l'EV estrès és només 0,0022 USDC/trade.

Decisió: `REJECT_TEMPORAL_AND_SMALL_ACCOUNT_FAIL`; no MC, no holdout, no Python.

### Sweep + reclaim nadiu v4–v5 (2026-08-03)

V4 és la primera campanya sota `alquimia-v3-native-evidence-chain`: cap pipeline
quantitativa antiga, Builder nou i gate sobre l'AST real. SQCLI va generar prop
de 4.000 estratègies i en va acceptar 20, però **0/20** implementaven exactament
el mateix extrem per al sweep i el reclaim. Això prova que una allowlist de blocs
no basta per generar una hipòtesi coordinada.

V5 fixa l'entrada long/short en un SQX nadiu i deixa optimitzables només lookback,
ATR i sortides. El Retester es va reparar eliminant la selecció TSLA residual;
el smoke SQ real acaba en 6,01 s, conserva l'AST i produeix 1.180 trades, amb
−1.037,71 de benefici train. Abans de llançar 5.000 optimitzacions, una malla
DuckDB sobre 18.448 H4 Dukascopy prova 1.350 punts i costos 8/12/20 bps més
funding 4/8/12% anual. Resultat: 0 PASS d'estrès i 0 regions estables.

El millor long (lookback 60, 12 barres, ATR14, stop/target 3×ATR) té 221 trades,
PF 1,149 i +17,88% base, però PF 0,878 i −18,51% en estrès. No té cap trade amb
ordre intrabar ambigu; M1 no pot rescatar aquest deteriorament. Short i combinada
ja són negatives en base. Decisió terminal `REJECT_FAMILY_V5`; validation, OOS i
holdout continuen segellats. L'Optimizer existeix però deliberadament no s'executa.

### Desplaçament H1 i reversió tardana v6–v7 (2026-08-03)

V6 prova una hipòtesi independent sobre 71.257 H1 Dukascopy: barres expansives
que tanquen a l'extrem, continuació o reversió, long/short/combinada, sis blocs
UTC, dies de la setmana, ATR14/28 i sortides 1/2/4/8 hores. S'executen 5.184
punts pre-registrats: 0 passen el gate d'estrès i cap punt té una regió estable.

La diagnosi separa barres escasses i detecta una possible reversió long després
d'un desplaçament baixista entre 20–24 UTC. Com que la regla deriva del train,
es congela com v7 i es declara explícitament el biaix de selecció; no s'optimitza.
Amb ≥50 M1 observades al senyal i entrada, train dóna 55 trades, PF estrès 1,84,
+6,10% i 7/10 anys positius. A la validació independent 2015-02-07–2019-07-16,
però, només conserva edge base: 20 trades, PF base 2,27; amb estrès PF 0,85,
−0,43% i 2/5 anys positius. V7 queda terminalment rebutjada sense consultar OOS
ni holdout. La diferència confirma que un edge d'uns 10,7 bps/trade no té marge
suficient per al pressupost conservador de costos d'Ostium.

### MSFT D1 gap/shock v8 — bloqueig de font (2026-08-03)

SQCLI exporta directament `MSFT` D1 del Data Manager, 6.936 files entre
1999-01-04 i 2026-07-31, amb SHA-256 congelat. El nou gate offline agrega les
candles M1 natives d'Ostium a sessió regular i compara OHLC sense Yahoo.

En 93 sessions completes, el close és coherent: diferència mediana 5,29 bps,
p95 24,34 bps, correlació de retorns 0,9979 i direcció 100%. L'open no passa:
mediana 29,36 bps i p95 116,30 bps. High i low tenen p95 229,52 i 178,78 bps,
amb diversos outliers d'oracle detectats. Això permetria recerca estrictament
close-only, però no una estratègia que defineix gaps, stops o execució a l'open.

V8 acaba amb `BLOCK` a `market_preflight`; no s'executa Builder ni es consulten
train/validation/OOS/holdout. El gate és reutilitzable per altres equities a
`sq_ostium_equity_parity.py`. El bloqueig només es pot aixecar amb un històric
Ostium/BS corregit o una font OHLC que superi els mateixos llindars congelats.

### Gate XAU/BTC i inside-day XAU D1 v9 (2026-08-03)

El gate de mercat reproduïble selecciona XAU només per a recerca: 6.885 M1
alineades entre Ostium i Dukascopy, correlació de retorns en mercat obert 0,971
i acord direccional filtrat 96,69%. El solapament és de només set dies, així que
`live_eligible` continua fals. BTC queda bloquejat perquè `BTCUSDT` de SQ no es
pot equiparar a BTC/USD d'Ostium sense històric nadiu de l'oracle.

V9 preregistra una hipòtesi geomètrica nova: ruptura del màxim/mínim d'un dia
interior D1 amb sessió 17:00 New York, filtre EMA opcional, entrada stop el dia
següent, stop/target ATR i sortida en 1–3 sessions. S'han calculat 1.944 punts
sobre 3.205 sessions de train (2004-01-02–2015-02-06), incloent 3/6/9 bps i
finançament anual 4/8/12%. Resultat: 0 punts passen i 0 regions estables.

Una auditoria posterior fixa l'invariant d'una sola posició oberta i regenera
la malla: el millor punt sota estrès és long amb PF 1,003; el millor short cau a
0,996. La conclusió es reforça. Decisió terminal: `REJECT_DISCOVERY`; no
s'executa SQCLI i validació,
OOS i holdout continuen segellats. La cadena verificable és
`lab/sq_bridge/evidence/xau_d1_inside_breakout_v9_chain.json`.

### XAU D1 trend-pullback v10 (2026-08-03)

V10 parteix d'una idea clàssica però genera evidència pròpia: RSI curt extrem
contra una tendència EMA100/200, entrada al següent open, una sola posició,
stop ATR i sortida en 1–3 sessions. La malla preregistrada de 324 punts produeix
25 PASS de train, tots long i dins un únic component estable: RSI2/3, durada
1/2 dies i stops 1–2 ATR.

Per no escollir el millor PF, un selector sense mètriques tria el medoid del
component: EMA200, RSI3 ≤10, stop 1,5 ATR, dues sessions. Train: 57 trades, PF
estrès 1,512, +13,37%, DD 6,23% i 7/9 anys positius. A la validació independent
2015-02-09–2019-07-16 només fa 11 trades, PF estrès 0,097, −6,46% i 0/3 anys
positius; l'expectativa cau de +23,16 a −60,35 bps.

La concentració del train en el cicle alcista de l'or 2004–2011 no es manté en
el règim 2015–2019. V10 queda `REJECT_TEMPORAL_VALIDATION`; OOS i holdout no
s'obren i SQCLI no s'executa. Cadena:
`lab/sq_bridge/evidence/xau_d1_trend_pullback_v10_chain.json`.

### Activació del recorder BTCUSD (2026-08-03)

BrokerageService ja implementava el recorder adequat sobre l'endpoint Ostium
`latest-price`; TradingAgent no el duplica. S'ha afegit `BTCUSD` amb hot-reload
`diff`, preservant els deu símbols existents i sense reiniciar serveis. L'oracle
confirma el feed BTC/USD i BS resol l'instrument com a `perp`. La verificació
inicial mostra ticks i candles escrits, zero errors i fitxers físics CSV/JSONL.

`ostium_native_coverage_gate.py` exigeix 60 dies, cobertura ≥90%, candle recent,
OHLC vàlid i absència de duplicats abans de `READY_FOR_PARITY`. La primera
captura té 6 M1 consecutives i 100% de cobertura, però queda `WARMING`; no podrà
madurar abans de 2026-10-02 08:34 UTC. Fins llavors no autoritza recerca.

El gate d'univers v2 també queda endurit: l'existència del directori BTC ja no
és suficient. Requereix maduració **i** un artifact explícit de paritat
BTCUSDT/BTCUSD. Això evita promocionar accidentalment una font acabada de crear.

La font SQ existent `BTCUSDT_M1.dat` (91.687.147 bytes, SHA congelat) falla una
exportació nativa amb SQ 143.2708: `Unknown logic type of value 3`. No s'ha
generat cap CSV ni modificat el `.dat`. Queda bloquejada fins reconstruir una
font separada i atribuïble; no es farà `update` destructiu sobre l'única còpia.

La reconstrucció separada ja té un primer tram verificat. El builder descarrega
els arxius mensuals oficials de Binance, valida el `.CHECKSUM`, normalitza els
timestamps i crea `BTCUSDT_BINANCE_M1` sense sobreescriure `BTCUSDT`. Juny de
2026 aporta 43.200 M1 consecutives; SQCLI n'importa i en reexporta exactament
43.200 amb timestamps idèntics. SQ arrodoneix OHLC a una dècima (error màxim
0,05 USD, negligible per a senyals BTC) i volum a enters, així que queda permès
només per recerca sense regles de volum. Paper/live continuen bloquejats fins a
maduresa del recorder, paritat BTCUSD/BTCUSDT i model d'execució Ostium.

### BTC proxy v11–v12 — falsificació abans de SQCLI (2026-08-03)

La font completa cobreix 2018-03-01–2026-06-30 amb 4.377.479 M1 i checksum per
cada arxiu mensual oficial. L'auditoria detecta 27 gaps reals (5.881 minuts,
màxim 600); cap timestamp es repara ni s'inventa. El motor només usa barres
completes dins de tot el lookback i descarta trades que travessen un gap. Les
anomalies desalineades de 2017 i febrer de 2018 s'exclouen abans de veure PnL.

V11 preregistra 1.032 punts de tres mecanismes independents, H1/H4/D1 i costats
separats: Donchian, pullback en tendència i breakout de compressió. Inclou 5 bps
d'obertura, impacte dinàmic 1/4/10 bps i rollover 8/20/40% anual. En train
2018-03–2021-12, 18 punts passen i només dues regions tenen veïnat estable:
compressió long H1 (medoid: 185 trades, PF estrès 1,27) i pullback long H4
(74 trades, PF 1,21). A la validació 2022–2023 ambdues reverteixen: PF 0,70 i
0,65, expectativa −20,6 i −36,0 bps. V11 queda rebutjada.

El canvi de règim no és només matemàtic: el 2022 va coincidir amb enduriment
monetari accelerat de la Fed. V12 declara aquesta observació i consumeix
2022–2023 com a desenvolupament; no el reutilitza com a validació. Prova 216
breakouts alineats amb el D1 anterior respecte EMA100/200. Una regió short H1
de tres punts sobreviu; el medoid (EMA200, canal 168h, sortida 36h, stop 1,5ATR)
té PF estrès 1,56 en desenvolupament. A la nova validació 2023-07–2024-06 només
fa 3 trades, tots perdedors: PF 0 i EV −102 bps. Aquest període inclou
l'aprovació dels ETP spot de bitcoin als EUA el gener de 2024, un règim alcista
materialment diferent. V12 també queda rebutjada.

Decisió reproduïble: `REJECT_BTC_PROXY_FAMILIES_NO_SQCLI`. OOS i holdout no
s'han consultat; SQCLI, small-account promotion i paper/live no s'executen. Els
fets de context provenen de les fonts primàries de la
[Reserva Federal](https://www.federalreserve.gov/publications/2022-ar-monetary-policy.htm)
i la [SEC](https://www.sec.gov/newsroom/speeches-statements/gensler-statement-spot-bitcoin-011023).
El cost actual s'ha recertificat contra la
[taula oficial d'Ostium](https://docs.ostium.com/traders/reference/markets):
BTC/USD és 5 bps d'obertura, fins a 200x, amb bid/ask dinàmic i rollover.

### BTC sessions v13–v14 i ampliació nativa ETH/SOL (2026-08-03)

V13 congela abans de calcular 288 ruptures de rang H1: blocs 00/08/16 UTC,
weekday/weekend, rang 2/4h, finestra 4/8h, stops 1,5/2,5 ATR, sortida 2/4/8h i
long/short separats. La millor variant de continuació sota estrès té 532 trades,
PF 1,03, EV +2,31 bps, DD 32,7% i només 3/7 anys positius. Resultat: 0/288 PASS.

V14 declara que deriva d'aquest fracàs i prova la inversió simètrica, sense
retunejar la malla: entrar contra el primer close fora del rang. Només 1/288
passa puntualment (short de cap de setmana 16 UTC, PF 1,23, 197 trades), però no
té dos veïns ortogonals bons. Altres punts amb PF 1,34–1,43 només són positius
4/7 anys. Resultat: 0 regions estables. No s'obre validació, OOS ni holdout i no
s'executa SQCLI. Això evita promocionar el punt aïllat per cherry-picking.

BrokerageService grava ara també ETHUSD i SOLUSD per hot-reload: 13/13 símbols
actius, primers ticks/candles físics, zero errors i cap ordre. Tots dos comencen
`WARMING` i no podran arribar a 60 dies abans de 2026-10-02 09:27 UTC. El
registre canònic incorpora ETH/USD (200x) i SOL/USD (150x), amb 5 bps; recerca
promotable i paper/live continuen bloquejats fins tenir paritat pròpia.

### Crypto multi-actiu v15–v17 i fonts SQ verificades (2026-08-03)

La següent branca no reutilitza resultats quantitatius antics. Parteix de CSV
M1 oficials de Binance, amb hash i control de buits: BTC 4.377.479 files
(2018-03–2026-06), ETH 3.938.630 (2019-01–2026-06) i SOL 3.064.335
(2020-09–2026-06). Els tres són proxies de recerca; els recorders Ostium natius
continuen `WARMING` i són el gate de promoció.

V15 prova 192 variants de momentum relatiu setmanal, ja escalades a 200 USDC,
risc d'stop de l'1%, oracle fix i costos Ostium: 0 PASS. V16 afegeix momentum
absolut i quedar-se en efectiu: 2/96 PASS aïllats, però cap regió estable. V17
declara el biaix de selecció i refina localment 225 punts: 16 PASS, 14 estables
i un medoid topològic de lookback 14 dies, hold 7, ATR21 i stop 3 ATR. En
desenvolupament fa 102 trades, PF estrès 1,19, EV +5,66 bps, +5,59% i 3/4 anys
positius. La validació independent 2024H2 reverteix: 18 trades, PF estrès 0,62,
EV -12,89 bps, -2,33% i 0/2 trimestres. Decisió terminal:
`REJECT_CRYPTO_MOMENTUM_NO_OOS_NO_SQCLI`; OOS 2025H1 i holdout 2025H2+ no
s'han obert.

ETH i SOL s'han importat a SQ 143.2708 en símbols nous, sense sobreescriure
fonts existents. Els roundtrips de juny de 2026 tenen 43.200/43.200 timestamps
i OHLC exactes. SQ trunca el volum fraccional (ETH 43.196 files; SOL 43.168),
per tant la decisió és `PASS_SIGNAL_RESEARCH`: es prohibeixen regles de volum,
paritat d'execució, paper i live. SOL requereix l'alta determinista prèvia de
l'instrument `SOLUSDT` amb tick `0,0001`; la recepta i els límits queden al
rebut `lab/sq_bridge/evidence/solusdt_sqcli_import_receipt.json`.

### Crypto compressió intradia v18 (2026-08-03)

V18 és una hipòtesi independent: després d'ATR H1 anormalment comprimit, prova
continuació i fade d'una ruptura de canal, long/short, blocs 00/08/16 UTC,
weekday/weekend i BTC/ETH/SOL. La malla de 2.304 punts es congela abans de
calcular. El notional surt d'arriscar l'1% de 200 USDC; el leverage és el màxim
enter permès pel venue que manté la liquidació almenys 1,25 vegades més lluny
que l'stop. Oracle de 0,10 USDC, fee 5 bps, impacte i rollover entren abans de
seleccionar.

Desenvolupament 2021–2024 produeix 17 PASS i dues regions de 3 membres. Els
medoids topològics són BTC breakout short, 00 UTC laborables (66 trades, PF
estrès 1,47, +0,37 USDC/trade, +12,45%, DD 7,51%) i ETH breakout long al mateix
bloc (62 trades, PF 1,70, +0,56 USDC/trade, +18,44%, DD 4,65%). Durada mediana
5 hores; leverage median 72,5x BTC i 52,5x ETH, marge median aproximat 1,26% i
0 liquidacions simulades.

La validació independent 2025H1 els falsifica: BTC només 6 trades, PF estrès
0,73, -0,41 USDC/trade i -1,30%; ETH 4 trades, tots perdedors, -1,32
USDC/trade i -2,61%. Decisió terminal:
`REJECT_CRYPTO_INTRADAY_COMPRESSION_NO_SQCLI`. No es tuneja, no s'executa
Builder i el holdout 2025H2–2026H1 continua segellat.

### Ledger temporal global i capitulació/reclaim v19 (2026-08-03)

`temporal_evidence_ledger.json` registra qualsevol període on s'han mirat
trades, PnL o selecció. Per BTC, ETH i SOL tot fins 2025H1 és ja pool de recerca
reutilitzable, mai més OOS independent. El bloc comú 2025H2–2026H1 queda
reservat per una sola cohort final. El gate permet inspeccionar preus natius per
paritat sense consumir holdout només quan no calcula senyals ni rendiments.

V19 preregistra 11.664 combinacions H1 price-only: shock direccional d'1/2/3%,
rang anormal respecte ATR, reclaim en 1/2/3 hores, blocs UTC, weekday/weekend,
long/short i BTC/ETH/SOL. No reutilitza thresholds ni evidència quantitativa de
`capitulation_d1`; només reutilitza el motor tècnic auditat de costos i sizing.
Discovery 2021–2022 dóna 20 PASS i una regió BTC long de 9 membres. El medoid
(shock -1%, rang 1,5 ATR, reclaim 50% en 2h, stop 1 ATR, hold 6h, bloc 00 UTC
laborable) fa 45 trades, PF estrès 1,60, +0,41 USDC/trade, +9,48%, DD 2,87%,
2/2 anys i 0 liquidacions.

El walk-forward intern 2023–2025H1 és atractiu agregat —27 trades, PF estrès
2,05, +12,43%, DD 4,22% i 0 liquidacions— però falla els gates congelats: 27<30
trades, 2023H2 només té 2<3 i només 3/5 folds són positius (mínim 4/5).
`REJECT_CRYPTO_CAPITULATION_RECLAIM_INTERNAL_WF`: no es relaxen llindars, no
s'executa SQCLI i el holdout global continua intacte.

## Pilot anterior

- `TA_SQ_PILOT`, original `NVIDIA` intacte.
- NVDA/USD confirmat a Ostium.
- `NVDAUSUSD_TICK_UTCMinus05`, M1, 147.024.593 ticks.
- Límit 20; manifest/hashes; límits 6 CPU/14 GB; una campanya.
- Watchdog: stop a 1.000 generades/0 acceptades, RAM host <1 GB o disc <2 GB.
- Generació correcta, sense errors tècnics; acceptació inicial 0%.

Proper gate: acabar o diagnosticar `ZERO_ACCEPTANCE`, exportar databank, construir
col·lector i paritat DuckDB/BS. Cap pas automàtic a paper/live.
