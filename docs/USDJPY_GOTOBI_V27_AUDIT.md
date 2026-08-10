# USDJPY Gotobi / Tokyo fixing v27

## Premissa externa

La premissa es va congelar abans de consultar rendiment. Ito i Yamada descriuen
el fixing de Tòquio de les 09:55 JST, el desequilibri persistent de demanda de
dòlars i la reversió posterior. Krohn, Mueller i Whelan documenten el patró
pre-fix/post-fix en diverses divises. Bessho, Sugimoto i Suzuki estudien
específicament els dies Gotobi divisibles per cinc.

- https://doi.org/10.1016/j.jinteco.2017.09.005
- https://doi.org/10.1111/jofi.13306
- https://arxiv.org/abs/2301.13204

Aquestes fonts justifiquen una hipòtesi; no són evidència que sigui rendible a
Ostium ni amb 200 USDC.

## Dades i mapping

- SQCLI 143.2708 exporta 7.170.956 M1 de `USDJPY_M1_dukas`, 2007–2026.
- Rellotge original EET/EEST normalitzat amb `Europe/Helsinki`: zero duplicats
  i zero OHLC invàlids.
- Una quarantena detectada només dins Ostium elimina el bucket H1 contaminat
  del 27/02/2026 i s'aplica simètricament als dos feeds.
- M15: 656 barres completes alineades, cobertura 98,35%, correlació 0,9961,
  direcció 98,45% i diferència close p95 0,92 bps. M15 passa per recerca;
  H1/H4 continuen bloquejats per cobertura completa.
- Snapshot SDK read-only: pair 4, fee 2 bps, màxim venue 100x, mínim 5 USD,
  spread observat ~1,25 bps i slippage simulat ~0,58 bps fins a 1.000 USD.

## Screen congelat

Vuit punts: calendari exacte o cap de setmana avançat a divendres, entrada
07:00/08:00 JST, stop 0,15%/0,25%, sortida 10:00 JST. Només train 2007–2014;
2015–2019, 2020–2023 i 2024–2026 no s'han consultat.

El millor punt (cap de setmana ajustat, 07:00, stop 0,25%) té 565 trades,
+1,86 bps bruts i +0,77 bps respecte dies no-event. Amb 5 bps base obté PF
0,62 i −0,251 USDC/trade; amb 15 bps + fallada de reemborsament de l'oracle,
PF 0,124 i −1,151 USDC/trade. Zero punts passen.

**Decisió:** `REJECT_NO_SQ`. No s'executa Builder, no s'augmenta leverage i no
s'obre cap tram posterior.
