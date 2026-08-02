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

El primer és el millor candidat de recerca, però el veredicte global continua
sent `LIVE_NOT_READY`: falta paritat OHLC/executiva nativa d'Ostium, probabilitat
de liquidació amb gaps, comparació aleatòria/calendari corregida per múltiples
proves, pertorbació de paràmetres i paper trading. Amb 200 USDC i risc màxim de
l'1%, `calendar 0.14` queda limitat aproximadament a 81,30 USDC de nocional. El
cap preliminar de 21× només redueix el marge requerit (~3,87 USDC); no autoritza
augmentar el nocional. Artifacts canònics: `msft_source_parity.json`,
`msft_python_validation.json`, `msft_finalists_holdout.json` i
`msft_final_gate.json` a `lab/out/alquimia/`.

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

## Pilot anterior

- `TA_SQ_PILOT`, original `NVIDIA` intacte.
- NVDA/USD confirmat a Ostium.
- `NVDAUSUSD_TICK_UTCMinus05`, M1, 147.024.593 ticks.
- Límit 20; manifest/hashes; límits 6 CPU/14 GB; una campanya.
- Watchdog: stop a 1.000 generades/0 acceptades, RAM host <1 GB o disc <2 GB.
- Generació correcta, sense errors tècnics; acceptació inicial 0%.

Proper gate: acabar o diagnosticar `ZERO_ACCEPTANCE`, exportar databank, construir
col·lector i paritat DuckDB/BS. Cap pas automàtic a paper/live.
