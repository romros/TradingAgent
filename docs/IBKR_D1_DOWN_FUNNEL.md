# Embut IBKR D1 cap avall

> **CAMPANYA V1 TANCADA.** Aquest document conserva metodologia i resultats
> d'IBUS500/SPY. No defineix l'univers v2 ni n'autoritza reutilitzar candidats.
> La continuïtat vigent és [`CURRENT_OBJECTIVE.md`](../CURRENT_OBJECTIVE.md).

Decisió de recerca del 2026-08-12: després de falsificar la generació genèrica
M15 i M30, la descoberta recomença a D1 i només baixa de timeframe quan existeix
una hipòtesi mare amb evidència.

Hi ha dos carrils seqüencials perquè una sola instància SQCLI no ha de competir
amb si mateixa:

1. `exploratory`: espai ampli de blocs traduïbles, separat en long, short i both.
   Serveix per descobrir patrons que no hem imposat, no per promocionar-los sols.
2. `profiled`: momentum temporal, reversió després de xoc i tendència en règim de
   volatilitat, cadascun long i short. Serveix per falsificar mecanismes amb una
   explicació econòmica prèvia.

El mínim train D1 és 60 operacions i el mínim OOS és 20. No es reutilitza el
llindar intradia de 250 perquè la freqüència possible és diferent. Es manté PF
train mínim 1,15 amb la comissió IBKR incorporada, SL obligatori, mida fixa 1 i
holdout segellat.

L'ordre de l'embut és `D1 → H4 → H1 → M30`. Baixar no significa copiar els
paràmetres: D1 defineix règim, direcció i mecanisme; el timeframe inferior només
pot millorar l'execució d'aquella mateixa idea. Una família que no passa D1 no
baixa, excepte una hipòtesi intradia independent i preregistrada.

Aturada: 10.000 avaluacions per branca o databank ple. Zero candidates és un
resultat vàlid. Les candidates només passen a validació temporal, robustesa,
economia de compte petit, traducció/paritat i paper; mai directament a live.

## Primer checkpoint real

El 2026-08-12 el carril exploratori va donar 20 candidates úniques LONG en
3.690 intents, 4 SHORT en 10.077 intents i 20 BOTH en 1.816 intents. El carril
perfilat va donar 20 momentum LONG en 1.450 intents, zero momentum SHORT en
11.857 intents i 20 shock-reversion LONG en 1.199 intents. Són supervivents de
train, no estratègies aprovades. El següent gate és deduplicació i validació
temporal; els resultats indiquen asimetria LONG clara i no justifiquen afluixar
cap filtre per rescatar SHORT.

## Checkpoint temporal i economia real — 2026-08-12

S'han retestat, sense filtres de rendiment dins SQ i sense obrir el holdout,
15 representants estructurals. Dues candidates LONG passen train, validation i
OOS amb costos de 2 USD per operació completa:

- `exploratory_long_11135`: PF OOS 1,417, 50 trades OOS i EV 22,29 USD;
- `voltrend_long_21100`: PF OOS 1,913, 40 trades OOS i EV 35,97 USD.

La parella té correlació diària 0,231 i passa el gate temporal de cartera. Les
dues candidates i la parella resisteixen costos de 4 USD i bootstrap de 2.000
mostres. Això és evidència estadística prometedora, no autorització de paper.

La mida mínima d'una unitat d'`IBUS500` invalida l'execució amb 2.000 USD. El
pitjor MAE observat és 13,41–14,24% del compte i el drawdown Monte Carlo P95 és
84–96% per estratègia. Amb els límits congelats, el capital mínim calculat és
17.874 USD per `voltrend_long_21100` i 18.982,67 USD per
`exploratory_long_11135`; domina el límit d'1,5% per trade, no el marge.

Per tant, no s'optimitzen paràmetres ni s'obre el holdout. La següent branca és
validar un vehicle IBKR de menor granularitat sobre el mateix underlying. La
primera hipòtesi és un Share CFD d'un ETF S&P 500 dels EUA. La disponibilitat
exacta del contracte al compte, la dada Dukascopy equivalent i la paritat de
trades SQ són gates obligatoris; no s'accepta escalar el PnL aritmèticament.

### Resultat del trasllat SPY

El retest uncensored sobre `SPY_benchmark.D` propietari de SQ conserva les
regles exactes, però falsifica el trasllat directe. Amb una participació i 2 USD
round-trip, `voltrend_long_21100` té PF train 0,935, validació 0,887 i OOS
1,444; `exploratory_long_11135` té 0,747, 0,913 i 1,063. La coincidència de
dates d'entrada amb US500 és només 60,0% i 65,1%.

Una participació limita el pitjor MAE a aproximadament 1,36–1,49% de 2.000 USD,
però no paga la comissió. De dues a deu participacions millora l'economia, però
cap mida passa simultàniament PF ≥1,20 als tres segments i risc ≤1,5%. SPY CFD
queda `REJECT_TEMPORAL_TRANSFER_AT_ONE_SHARE` i `REJECT_SPY_INTEGER_SIZING`.
La dada continua en quarantena perquè SQ en prohibeix l'exportació i el contracte
del compte IBKR encara no està verificat. No s'obre holdout ni s'optimitza.

La descoberta directa posterior també queda falsificada abans de validació:
una branca genèrica LONG va acceptar 0 de 10.015 intents i la branca de
volatilitat LONG, 0 de 11.155. Amb mida fixa d'una participació, comissió de
2 USD incorporada, ≥60 trades i PF train >1,20, SQ no troba cap candidata.
No es relaxen els gates. El següent mercat a preflight és EUR/USD CFD, però
IBKR publica 2 USD mínims per ordre (4 USD round-trip) i no publica prou clar el
mínim de contracte CFD sense consulta al compte. No es gastarà SQ per IBKR fins
qualificar el contracte exacte via API paper.
