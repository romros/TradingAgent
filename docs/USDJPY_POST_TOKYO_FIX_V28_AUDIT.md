# USDJPY post-Tokyo-fix reversal v28

## Pregunta congelada

La v28 comprova una direcció diferent de la Gotobi v27: venda incondicional
d'USDJPY després del fixing de Tòquio de les 09:55 JST. L'entrada és a les
10:00 JST i la sortida a les 14:00 o 16:00, amb stops de 0,20%, 0,30% o
0,40%. Són sis intents exactes sobre desenvolupament 2015–2018.

Ito i Yamada i Krohn, Mueller i Whelan justifiquen la premissa de demanda
pre-fix i reversió post-fix. Són inspiració per falsar una hipòtesi, no prova
de rendibilitat a Ostium.

- https://doi.org/10.1016/j.jinteco.2017.09.005
- https://doi.org/10.1111/jofi.13306

## Resultat observat

Cada punt produeix 1.038–1.039 operacions. El retorn brut mitjà és positiu però
petit: de +0,8610 a +1,8055 bps per operació. Amb 5 bps round-trip base, tots
els punts són negatius: PF màxim 0,6785 i millor EV −0,1809 USDC per operació.
Amb 15 bps d'estrès, PF màxim 0,2248, millor EV −0,7809 USDC i zero anys
positius. No hi ha cap liquidació simulada, però el drawdown supera àmpliament
el límit perquè l'expectativa és negativa.

Validació 2019–2021, OOS 2022–2023 i holdout 2024–2026 no s'han consultat.

## Decisió

`REJECT_NO_SQ`: zero de sis punts superen el gate congelat. El patró temporal
brut queda contradit per l'economia executable d'un compte de 200 USDC. No es
pot rescatar amb més apalancament perquè aquest multiplica una expectativa
neta negativa.

La línia completa de timing del fixing de Tòquio queda tancada: v27 rebutja el
pre-fix Gotobi long i v28 rebutja el post-fix short. No s'executa Builder, no
s'obre cap tram posterior i no s'ajusten hores, stops, calendari ni costos.
