# Campanya intradia FX — resultat final

**Data:** 2026-08-01
**Decisió:** `NO_CANDIDATE`

## Què s'ha provat

S'han explorat sis famílies sobre EURUSD i XAUUSD en 4H, amb dades M1 locals
agregades, entrada a la barra següent, 2004–2013 per desenvolupament,
2014–2019 per validació i 2020–2026 com a test final. El simulador incorpora
gas fix, spread/slippage, finançament, liquidació, capital compost, drawdown i
costos estressats.

El sweep respecta els límits retornats pel preflight local de BrokerageService:
màxim 10x i 50 USD de col·lateral per un compte de referència de 250 USD.

## Resultat de les sis famílies

Cap família produeix una configuració que, seleccionada només amb
desenvolupament, conservi EV positiva amb costos 2x i DD <=20%. Per tant, cap
leverage arriba legítimament al gate de validació i totes queden rebutjades:

| Família | Decisió |
|---|---|
| Reversió Bollinger/RSI | REJECTED |
| Breakout Donchian | REJECTED |
| Pullback en tendència | REJECTED |
| Expansió de volatilitat | REJECTED |
| Reversió de barra gran | REJECTED |
| Creuament de mitjanes | REJECTED |

## Auditoria de la millor quasi-candidata

La configuració més prometedora abans d'aplicar tots els límits és expansió de
volatilitat EURUSD `(ATR 2x, lookback 12)`, manteniment de 6 barres (24 hores),
10x i 20% de col·lateral (50 USD).

| Tram | Trades | PF base | EV/trade | Capital final | DD màx. | PF costos 2x |
|---|---:|---:|---:|---:|---:|---:|
| Desenvolupament | 206 | 1,22 | +0,23 USD | 296,39 USD | 15,7% | 0,85 |
| Validació | 141 | 0,48 | -0,60 USD | 164,82 USD | 34,1% | 0,33 |
| Test | 115 | 0,75 | -0,25 USD | 221,43 USD | 18,0% | 0,50 |

La validació perd cinc dels sis anys. El bootstrap de l'EV mitjana al 95% és
[-0,99, -0,22] USD per trade: fins i tot el límit superior és negatiu. En test
només tres de set anys són positius. Separar long/short no rescata el resultat:
en validació PF long 0,24 i short 0,88; en test PF long 0,92 i short 0,56.

No falla per proximitat a liquidació: MAE P99 és 2,03% en validació i 1,37% en
test, lluny del 10% teòric a 10x. Falla perquè l'edge de desenvolupament no es
repeteix i els costos fixos són massa importants per al nominal d'un compte
petit. Augmentar leverage no és una solució: BS el limita a 10x i amplificar
una expectativa negativa només augmenta la pèrdua.

## Estat operatiu de BrokerageService

La consulta `preflight` local per EURUSD i XAUUSD retorna actualment
`ready=false`: el quality gate recent informa de buits i l'adaptador Ostium no
està disponible; el mode és paper i live està desactivat. Això impedeix un
paper probe immediat, però no altera la decisió quantitativa: les estratègies
ja fallen amb les dades històriques.

## Decisió i següent pas

- No promoure cap de les sis famílies a TradingAgent ni a paper trading.
- No usar leverage per intentar convertir aquestes pèrdues en rendibilitat.
- Conservar l'expansió de volatilitat només com a hipòtesi rebutjada.
- La següent campanya hauria de canviar la font d'edge, no afinar aquests
  paràmetres: per exemple carry/roll, sessió horària, breakout amb stop
  explícit o una cartera setmanal multi-actiu, amb un test temporal nou.
- Abans de qualsevol paper trading cal reparar el preflight de BS.

## Evidència reproduïble

- Protocol: `lab/docs/INTRADAY_FX_RESEARCH_PROTOCOL.md`
- Runner: `lab/studies/intraday_fx_campaign.py`
- Auditoria: `lab/studies/intraday_fx_audit.py`
- Resultats: `lab/out/intraday_fx_campaign/results.json`
- Auditoria detallada: `lab/out/intraday_fx_campaign/near_candidate_audit.json`
