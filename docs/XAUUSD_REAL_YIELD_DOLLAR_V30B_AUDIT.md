# Auditoria de sensibilitat XAU/USD real yield + dòlar v30b

La v30 principal d’Academia es va executar concurrentment amb una regla fixa
d’una setmana, LBMA i 35 bps, i va perdre fins i tot abans de costos. Aquesta v30b
és una auditoria independent que ja estava preregistrada abans de conèixer aquell
resultat: usa episodis persistents, Dukascopy M15 i economia Ostium de 200 USDC.
No rescata, substitueix ni reobre la v30; comprova si la mateixa conclusió depèn
del proxy d’execució.

## Decisió

`REJECT_NO_SQ`. La família queda tancada en desenvolupament. No s’ha executat
StrategyQuant i no s’han carregat validació 2015–2018, OOS 2019–2022 ni holdout
2023–2026.

## Hipòtesi i informació disponible

La hipòtesi congelada era bilateral: caigudes simultànies del real yield americà
a 10 anys i del dòlar ampli afavoreixen XAU; pujades simultànies el perjudiquen.
Les fonts són `DFII10` i `DTWEXBGS`. La Reserva Federal publica l’H.10 els dilluns
a les 16:15 ET amb les dades de la setmana anterior, o el següent dia hàbil quan
el dilluns és festiu. Per això l’entrada no es permet fins dimecres 00:00 UTC.

Fonts oficials:

- [Federal Reserve H.10](https://www.federalreserve.gov/releases/h10/)
- [Federal Reserve H.10 — índexs del dòlar](https://www.federalreserve.gov/releases/h10/summary/)
- [U.S. Treasury — real yield curve](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics)

La passada macro no va mirar XAU: 417/417 setmanes train completes, 27 punts
congelats i 13 supervivents dins regions de freqüència. Només aquests 13 van
entrar al test de rendiment 2007–2014.

## Execució i compte petit

- Capital: 200 USDC.
- Risc: 1,5%, és a dir, 3 USDC per operació.
- Stop: 5%.
- Nocional: 60 USDC; exposició efectiva 0,3×.
- Leverage de venue: 14× sobre 50× màxim; marge aproximat 4,29 USDC.
- Cost base: 4,18 bps + 0,10 USDC d’oracle.
- Conservador: 8 bps + 0,10 USDC + 8% anual de carry.
- Estrès: 15 bps + 0,10 USDC + 12% anual de carry.
- El crèdit long observat en l’snapshot actual es limita a zero: no s’extrapola
  cap benefici de rollover actual cap al passat.

La font XAU conté 204.751 M15 derivades de 96 particions M1. Dukascopy pot ometre
minuts sense ticks; no s’imputen. Cada barra usada exigeix almenys una observació,
el gap màxim és 73,25 h sota el límit preregistrat de 74 h, i el stop es comprova
contra l’obertura següent després d’un gap. Una operació del millor punt es va
ometre perquè no tenia exactament l’entrada o sortida executable; 2,70% queda sota
el màxim congelat del 5%.

## Resultat millor, sense promoció

El punt 13 setmanes / 25 bps / 0,5% és el millor sota estrès:

| Escenari | PF | EV USDC/trade | PnL net | Anys positius |
|---|---:|---:|---:|---:|
| Base | 1,613 | +0,437 | +15,72 | 3/8 |
| Conservador | 1,221 | +0,176 | +6,34 | 3/8 |
| Estrès | 1,016 | +0,014 | +0,50 | 3/8 |

Són 36 operacions, DD d’estrès 7,18% i zero liquidacions. El brut és +20,33
USDC, però l’estrès consumeix 6,84 USDC en execució/oracle i 12,98 en carry.
No arriba a PF 1,05, EV +0,10 ni 75% d’anys positius, i no té veïns que passin.

El diagnòstic també és asimètric: en estrès, el costat long aporta +9,68 USDC i
el short −9,18. Eliminar el short ara seria una selecció post-hoc, no una prova
independent. Per tant queda explícitament prohibit rescatar v30b canviant cost,
direcció, llindars o obrint períodes futurs.

## Conclusió

Hi ha una relació bruta econòmicament plausible, però no un component robust i
executable per al catàleg. La metodologia ha fet la seva feina: ha detectat el
mecanisme abans de gastar SQCLI i l’ha aturat quan la concentració temporal i
els costos han invalidat la transferència.
