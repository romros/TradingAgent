# XAUUSD FOMC reaction v29

## Font externa i calendari

La família utilitza únicament comunicats de reunions FOMC regulars conegudes ex
ante. El parser llegeix calendaris oficials de la Reserva Federal, exclou
`unscheduled`, `cancelled`, `notation vote` i `conference call`, i fixa hashes
de set pàgines de calendari. Dues pàgines oficials de roda de premsa, 2015 i
2025, corroboren que el comunicat es va publicar a les 14:00 ET.

Resultat: 92 comunicats regulars entre 2015 i el 10/08/2026. Desenvolupament
2015–2018 conté 32 esdeveniments. Dos tenen un minut absent al feed Dukascopy i
queden exclosos sense imputació; 30 superen el mínim congelat de 24.

## Mapping i economia

El recorder XAU d'Ostium contenia cinc buckets de rollover contaminats. El
detector intern, sense mirar Dukascopy, identifica salts >8 bps a 16:55–17:35
NY i exclou els buckets M15 simètricament dels dos feeds. Després:

- 604 barres M15 completes alineades;
- cobertura 97,73%;
- correlació de retorns 0,9979;
- direcció 96,80%;
- diferència close p95 1,87 bps.

M15 passa per recerca; H1 continua bloquejat. Ostium confirma pair 5, mínim
5 USD i màxim venue 50×. Una sola captura de costos és provisional; per això es
conserven 8/15/30 bps i 0,10 USDC d'oracle només en estrès.

## Screen congelat

Setze punts exactes: reacció 15/30 minuts, continuació/reversió, hold 60/120
minuts i stop 0,50/0,75%. Capital 200 USDC, risc 1,5%, stop abans de liquidació,
venue leverage màxim 50× i marge 4–6%.

Les vuit reversions perden ja a 8 bps. Les vuit continuacions són positives a
8 bps. La millor és 15 minuts de reacció, continuació 120 minuts i stop 0,75%:

| Escenari | PF | EV USDC/trade | Anys positius |
|---|---:|---:|---:|
| Base 8 bps | 2,35 | +0,59 | 3/4 |
| Conservador 15 bps | 1,56 | +0,31 | 3/4 |
| Estrès 30 bps + oracle | 0,57 | −0,39 | 2/4 |

No hi ha liquidacions simulades. Zero de setze punts supera el gate d'estrès.

## Decisió

`REJECT_NO_SQ`. És la quasi-candidata nova més interessant, però no compleix el
contracte preregistrat i no s'envia a StrategyQuant. No es relaxen costos, no
s'afegeixen filtres i no s'obren validació 2019–2021, OOS 2022–2023 ni holdout
2024–2026.
