# US500 VIX risk-state v35 — preflight

## Decisió

`PASS_VIX_DATA_TIMING`. El CSV diari oficial de Cboe conté 9.246 sessions entre
02/01/1990 i 07/08/2026, sense dates duplicades, caps de setmana ni tancaments
invàlids. No s'ha consultat rendiment US500 ni definit cap regla.

## Ús temporal congelat

El VIX mesura volatilitat esperada a 30 dies a partir de quotes d'opcions SPX.
Per a la futura recerca, el tancament VIX d'una sessió només podrà afectar la
primera sessió US500 posterior. Queda prohibit unir VIX i US500 per la mateixa
fila diària o reconstruir intradia a partir d'OHLC diari.

Fonts oficials:

- [Cboe — VIX historical data](https://www.cboe.com/tradable-products/vix/vix-historical-data)
- [Cboe — VIX FAQ i metodologia temporal](https://www.cboe.com/tradable-products/vix/faqs)

## Anomalia quarantinada

Hi ha 47 files antigues on `OPEN` no és coherent amb `HIGH/LOW`, inclosos valors
clarament sospitosos. No es corregeixen ni s'usen. El camp preregistrat `CLOSE`
és finit i positiu a les 9.246 files; qualsevol futura extensió que necessiti
open/high/low haurà d'obrir un gate nou.

## Límit

Aquest pass només prova font, cobertura i política anti-look-ahead. La definició
d'una família de baixa rotació continua bloquejada fins completar el gate real
de spread open/midday/close d'Ostium durant tres dies diferents.
