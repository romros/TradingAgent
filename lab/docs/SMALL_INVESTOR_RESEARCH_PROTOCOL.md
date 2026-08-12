# Protocol de recerca per a petit inversor

## Objectiu

Trobar entre 4 i 8 estratègies simples, auditables i poc correlacionades. No es
força cap nombre mínim de candidates: una estratègia només passa si conserva
expectativa positiva fora de mostra després de costos i amb risc controlat.

L'univers promocionable exclou criptomonedes. Només admet sintètics d'Ostium
referenciats a divises, metalls, índexs o accions amb mapping i paritat certificats.

## Divisió temporal immutable

- Desenvolupament: inici de dades fins a 2017-12-31.
- Validació: 2018-01-01 fins a 2022-12-31.
- Test final: 2023-01-01 fins a l'última sessió completa disponible.
- El test final es consulta una sola vegada i no s'utilitza per canviar regles,
  actius, paràmetres ni leverage.

## Univers inicial

ETF líquids i comprensibles: SPY, QQQ, IWM, GLD i TLT. Les primeres candidates
són long/cash, sense venda en curt. Abans de paper trading s'ha de confirmar que
BrokerageService pot executar l'instrument o un proxy equivalent.

## Model d'execució

- La regla només utilitza informació disponible al tancament.
- L'entrada s'executa a l'obertura de la següent sessió real.
- No es creen entrades en caps de setmana ni festius.
- Cost base i cost estressat (2x) inclouen fee, spread i slippage.
- El finançament del leverage es carrega per cada nit mantinguda.
- Capital inicial candidat: 200, 300, 400 o 500 USDC; se selecciona el menor que
  superi mínims d'ordre, costos, marge i gates de risc. La comparació també ha
  d'informar l'eficiència de capital de cada opció. També es resimula amb 1.000
  USDC com a primera fita i com a alternativa de capital inicial.

## Pla fins a 1.000 USDC

La projecció presenta per separat: compounding sense aportacions, compounding
amb aportacions d'estalvi configurables i inici directe amb 1.000 USDC. Ha de
mostrar escenaris conservador, central i advers, incloent temps fins a la fita,
drawdown i probabilitat de ruïna. Les aportacions no es poden comptar com a PnL.

Quan el saldo arribi a 1.000 USDC, es repeteix el gate de cartera i es redueix el
leverage sempre que la major base de capital permeti conservar el mateix risc
monetari i l'estratègia continuï sent viable després de costos.

Preferència de l'operador: tram 200→500 agressiu assumint que els 200 USDC són
capital especulatiu; tram 500→1.000 progressivament més conservador; a partir de
1.000, preservació. La simulació ha d'escollir el risc agressiu per probabilitat
d'arribar a la fita abans del límit de pèrdua, no pel PnL màxim retrospectiu.

Es prioritzen trades curts i oportunistes condicionats per un règim observable
abans de l'entrada. No són promocionables si l'expectativa neta desapareix amb
costos conservadors. El filtre de règim i l'horari formen part de la regla
congelada i no es poden justificar retrospectivament amb notícies ja conegudes.

## Selecció de leverage

El leverage es prova després de congelar la lògica de l'estratègia. Sweep
inicial: 1x, 1.5x, 2x, 3x, 4x, 5x, 7.5x, 10x, 15x i 20x, limitat al màxim real
del venue.

Se selecciona **el leverage més alt que compleixi tots els límits**, no el que
produeixi el PnL històric més alt:

- cap ruïna ni capital per sota del mínim operatiu;
- liquidacions: 0% al test final i <=1% en desenvolupament+validació;
- max drawdown <=20% en validació i <=25% al test final;
- pèrdua mensual P95 <=10% del capital;
- expectativa positiva amb costos estressats 2x;
- profit factor >=1.20 en validació i test final;
- cap any o règim individual explica més del 50% del benefici total;
- buffer de liquidació: MAE P99 <=50% de la distància teòrica de liquidació;
- el mateix leverage ha de passar un bootstrap/Monte Carlo conservador.

Si cap leverage superior a 1x passa, la candidata queda a 1x. Si 1x tampoc
passa, es rebutja. El leverage no es reajusta mirant el test final.

## Gate d'estratègia

- Tesi econòmica clara i màxim 3 paràmetres sensibles.
- Resultat positiu en desenvolupament, validació i test final.
- Profit factor >=1.25 en validació i test.
- Cost estressat 2x encara positiu.
- Paràmetres veïns: >=70% de variants positives en validació.
- Walk-forward: >=65% de finestres positives.
- Mostra mínima per a estratègies discretes: >=40 operacions totals, >=10 en
  validació i >=8 al test final. Les carteres de rebalanç periòdic han de tenir
  almenys 36 rebalancejos a cada tram fora de desenvolupament.
- No dependre d'un únic actiu escollit després de veure el test.

## Gate de cartera

- Entre 4 i 8 estratègies; començar en paper amb les supervivents reals.
- Correlació de retorns <=0.65 quan sigui possible.
- Cap estratègia aporta més del 40% del risc total.
- Leverage agregat i risc simultani limitats; no se sumen cegament els màxims
  individuals.
- Drawdown de cartera <=15% en validació i <=20% al test final.
- Paper trading de fins a 14 dies naturals abans de qualsevol capital real. És
  un gate de paritat i operació, no el substitut de l'evidència històrica; no
  s'exigeix una mostra mínima de trades quan la freqüència sigui baixa.

## Regla de decisió

Un resultat espectacular no compensa una violació del protocol. Si no hi ha
prou candidates, el resultat correcte és `NO CANDIDATE`, no relaxar el gate.
