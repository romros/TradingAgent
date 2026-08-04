# Objectiu econòmic: x2 amb supervivència

**Estat:** preregistre de cartera, 2026-08-04. No és una promesa de rendiment.

## Funció objectiu

Minimitzar el temps medià i la cua adversa per duplicar el capital, no maximitzar
el backtest. Una candidata o cartera només compta si incorpora fills executables,
fees, oracle, spread/impact, rollover, mida mínima i liquidació d'Ostium.

Referències matemàtiques per duplicar: 100% anual en 1 any, 41,42% en 2,
25,99% en 3, 18,92% en 4 i 14,87% en 5. L'objectiu de recerca és trobar una
cartera realista de 4–8 edges independents capaç d'apropar-se al 15–25% net
anual; l'evidència actual encara no ho demostra.

## Restriccions abans de comparar temps a x2

- probabilitat simulada de ruïna inferior a l'1%;
- liquidacions en estrès com a màxim 0,1% i cap en la mostra històrica central;
- drawdown de cua (percentil 95) màxim 25–30%;
- risc simultani de cartera màxim 3% sota 1.000 USDC;
- cap edge o règim explica més del 35% del benefici esperat;
- validació temporal, règims, Monte Carlo, costos d'estrès i paper independent;
- leverage derivat de MAE/stop i risc monetari, mai del màxim ofert pel venue.

## Política provisional de capital

Sota 1.000 USDC es pot estudiar un pressupost agregat agressiu de fins al 3%,
però només repartit entre edges validats i no correlacionats. En arribar a 1.000,
baixar cap a l'1%. Si només existeix `capitulation_d1`, no s'utilitza tot aquest
pressupost: la manca de diversificació és un límit, no una invitació a triplicar
la mida.

## Evidència disponible

`capitulation_d1` és l'única candidata en paper i només acumula sis operacions.
La reconstrucció històrica conservadora és aproximadament 1,22% CAGR a risc 1%;
no sosté un x2 ràpid. `msft_close_drift_v24` queda exclosa de qualsevol projecció:
necessita el close de 16:00 ET, posterior al tall day-trade Ostium de 15:45, i el
seu model de 36 bps no reflecteix l'oracle fix de 0,10 USD en un compte petit.

## Regla de decisió

Primer se seleccionen carteres que passen totes les restriccions. Només entre
aquestes es minimitza el temps a x2 mitjançant bootstrap/Monte Carlo amb intervals,
incloent la probabilitat de no duplicar en 3, 5 i 10 anys. Si cap cartera passa,
el resultat correcte és `NO_CANDIDATE`, no més leverage.
