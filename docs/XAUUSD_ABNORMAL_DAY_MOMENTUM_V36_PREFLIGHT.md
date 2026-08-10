# XAUUSD abnormal-day momentum v36 — preflight

## Decisió

`PASS_RESEARCH_PROXY_ONLY`. Es pot executar un únic screen de train amb la
família congelada, però no StrategyQuant, validació, OOS, holdout o paper. En
aquest preflight no s'ha llegit rendiment XAU històric.

Errata executable, congelada encara sense rendiment: el senyal es calcula amb
el close M15 complet de 09:45/11:45 i l'ordre entra al següent open de
10:00/12:00. Així no s'utilitza el mateix preu futur per detectar i omplir.

## Per què aquesta hipòtesi

Caporale i Plastun documenten continuació durant les últimes hores de jornades
anormals de l'or. És una explicació plausible de price discovery sota informació
nova, té poca rotació i evita mantenir la posició durant dies. L'article publicat
usa 2009–2020, però no és una prova transportable a 2026: inclou la recuperació
post-2008, la pujada i caiguda de l'or de 2011–2013, el règim de tipus molt baixos
i l'inici de la COVID. Avui el nivell nominal de l'or és molt superior i la
microestructura és diferent; per això el llindar és relatiu a volatilitat i no a
dòlars o percentatges fixos.

La font principal també té limitacions severes: dades MetaQuotes GMT+3, timings
estimats amb la mostra completa, absència de costos i cap walk-forward. A més,
la reversió de l'or l'endemà no era estadísticament diferent del trading aleatori.
Aquesta branca queda descartada abans de qualsevol càlcul propi. Un altre estudi
dels mateixos autors troba que patrons intradia genèrics desapareixen quan
s'inclouen spreads; això justifica el gate de 30 bps.

Fonts:

- [Caporale i Plastun (2021)](https://doi.org/10.1007/s11408-021-00380-w)
- [CESifo 4752 — control negatiu de costos](https://www.ifo.de/en/cesifo/publications/2014/working-paper/intraday-anomalies-and-market-efficiency-trading-robot-analysis)

## Regla congelada abans de rendiment

La sessió segueix el rellotge executable d'Ostium a Nova York: comença amb el
primer M15 complet de les 18:15, després de la pausa diària, i acaba abans de la
pausa següent. Amb el close de 09:45 o 11:45 es compara el retorn parcial amb la mitjana i
desviació estàndard de 40/80/120 sessions ja completades. Només si supera
`mitjana ± 1,5/2/2,5σ` s'entra al següent open en continuació. Sortida a stop 0,75%/1% o 16:45.
Són exactament 36 punts; no se n'afegiran després de veure train.

Train queda limitat a 2007–2014. Validació 2015–2018, OOS 2019–2022 i holdout
2023–2026 romanen segellats. Els costos són 8/15/30 bps i el sizing és de 200
USDC, risc 1,5%, marge màxim 35%, reserva mínima 40% i liquidació exacta. Ostium
permet fins a 50x, però això és un límit del venue, no l'apalancament escollit.

## Evidència de transport

El mapping M15 Dukascopy↔Ostium té 604 barres completes, cobertura 97,73%,
correlació de retorn 0,9979 i diferència close p95 1,87 bps. La captura live
observa fee 2 bps, spread 1,27 bps i impacte 0,68 bps a 200 USDC; encara és només
una instantània provisional. Per això els 8/15/30 bps són falsadors prudents i
un PASS de recerca no podria autoritzar paper.

Configuració definitiva preregistrada SHA-256:
`342c5b0a9dabd7a63310e1678b1a0f241957c6b1d2aca21bb32159c8313787da`.

## Resultat de la porta històrica

`BLOCK_DATA_COVERAGE`, abans de discovery vàlida. De 2.022/2.023 sessions amb
els quatre timestamps estructurals, només 855/859 conserven tots els M15
complets necessaris: 42,28%/42,46%. El problema és especialment greu entre
2007–2010 (6–52 sessions anuals) i reapareix el 2013. El contracte mínim és 90%
global i 80% a cada any; no passa.

Un primer càlcul local no versionat va arribar indegudament a les 36 mètriques
abans que detectéssim aquesta mancança. Va donar zero supervivents formals, però
queda invalidat i no s'utilitza ni per rebutjar ni per ajustar la hipòtesi. No es
canvia la font, el split o els llindars després d'haver-lo vist. La cadena v36
queda terminal `BLOCK`; validació, OOS, holdout, SQCLI i paper continuen intactes.
