# IBKR Espanya — cartera experimental de 1.000 USD

> **ESTUDI V1 HISTÒRIC.** Les observacions jurídiques i de sizing requereixen
> reverificació abans d'usar-les. L'objectiu i els capitals vigents són a
> [`CURRENT_OBJECTIVE.md`](../CURRENT_OBJECTIVE.md).

**Estat:** disseny i preregistre. No autoritza operativa real ni promet una
rendibilitat periòdica.

## Viabilitat jurídica i tècnica

Interactive Brokers Ireland Limited consta al registre oficial de la CNMV amb
el número 5023 com a empresa de l'EEE en lliure prestació de serveis a Espanya.
IBKR ofereix Web API i TWS API (inclòs Python) a clients particulars per llegir
compte i mercat i enviar ordres programàticament. L'accés final a cada producte
depèn de l'aprovació del compte, experiència declarada i permisos de negociació.

Fonts verificades el 2026-08-11:

- https://www.cnmv.es/Portal/Consultas/ESI/ESISExtranjerasLP?numero=5023&tipo=CLP
- https://www.interactivebrokers.ie/es/index.php?f=6605
- https://www.interactivebrokers.ie/es/accounts/trading-and-market-data.php

## Resultat que es pot defensar avui

No hi ha evidència per garantir un percentatge setmanal o mensual. Una promesa
del 1% setmanal equival aproximadament al 67,8% anual compost; un 2% mensual,
al 26,8% anual. Són objectius de recerca, no rendiments esperables.

La cartera IBKR no es declara `LIVE_READY` perquè:

1. `capitulation_d1/MSFT` és l'única candidata acceptada del projecte i només
   té sis trades paper;
2. la seva economia es va calcular per Ostium a 20x, no per IBKR;
3. una acció US mantinguda overnight té normalment marge Reg T del 50% (aprox.
   2x), subjecte a models de risc i requisits interns d'IBKR;
4. amb 1.000 USD, mínims de comissió, conversió de divisa i dades poden dominar
   estratègies freqüents o ordres europees petites.

Hi ha, a més, un bloqueig operatiu determinant: IBKR publica un mínim de
**2.000 EUR per operar amb qualsevol compte de marge europeu**. Per tant, una
cartera live iniciada amb 1.000 USD no pot pressupostar leverage d'IBKR. Sí que
podem investigar-la i executar-la al compte paper, o operar a 1x amb un compte
cash mentre s'acumula capital fins al mínim del compte de marge.

Font verificada el 2026-08-11:

- https://www.interactivebrokers.ie/en/trading/margin-stocks.php?ex=eu&hm=eu&pm=0&rgt=1&rsk=1&rst=121204040808080808

## Cartera provisional per fer paper i mesurar

La cartera és una arquitectura de capital, no quatre estratègies inventades:

| Compartiment | Pes màxim | Funció |
|---|---:|---|
| Nucli UCITS global acumulatiu | 70% | Exposició diversificada de llarg termini |
| Reserva en efectiu | 20% | Comissions, marge i noves oportunitats |
| `capitulation_d1/MSFT` | 10% de collateral, 20% nominal màxim | Únic edge tàctic actual; només paper |

Regles:

- compte cash durant la integració i el primer paper; marge només després de
  superar 2.000 EUR i recalibrar MAE, stop, interessos i liquidació amb dades
  IBKR;
- risc inicial per trade: 0,5% de l'equity (5 USD); màxim agregat: 1%;
- cap venda en curt, opció, futur, CFD ni producte cripto;
- cap ordre real fins a tenir paritat de senyal, preu, comissió i fill;
- els dividends i beneficis queden al compte: el sizing es recalcula sobre
  l'equity actual, que és el compounding;
- revisió mensual, sense forçar trades per fabricar un retorn mensual;
- si el cost estimat d'anada i tornada supera el 20% del benefici brut esperat,
  l'ordre queda bloquejada;
- drawdown del 5%: reduir risc a la meitat; drawdown del 8%: aturar noves
  entrades i auditar; pèrdua mensual del 4%: circuit breaker.

El nucli no s'ha de comprar automàticament fins a seleccionar un ETF UCITS que
el compte concret pugui negociar, comprovar KID/PRIIPs, divisa, borsa, TER,
spread, fraccions i comissió. Amb només 1.000 USD es prefereix un únic ETF ampli
a fragmentar la cartera i pagar múltiples mínims.

## Objectius i criteris de promoció

La referència honesta és superar, després de costos i amb menys drawdown, un
benchmark UCITS global comprat i mantingut. Els percentatges següents són
escenaris de planificació, no previsions:

| Retorn net anual | 1.000 després d'1 any | 2 anys | 3 anys |
|---:|---:|---:|---:|
| 5% | 1.050 | 1.103 | 1.158 |
| 10% | 1.100 | 1.210 | 1.331 |
| 15% | 1.150 | 1.322 | 1.521 |
| 25% | 1.250 | 1.563 | 1.953 |

Per passar de paper a capital real, la part tàctica ha de mostrar:

- reproducció exacta dels senyals entre recerca i runtime;
- costos IBKR observats, no estimats, i almenys 30 fills o evidència històrica
  executable suficient amb un paper mínim de dues setmanes;
- expectativa neta positiva sota costos 2x, profit factor >= 1,25 i cap
  dependència d'un sol any;
- drawdown històric i Monte Carlo compatibles amb els circuits anteriors;
- millora respecte al benchmark després d'ajustar per risc.

Si no passa, la decisió és mantenir només el nucli diversificat i continuar la
recerca. No s'augmenta el leverage per compensar absència d'edge.

## Construcció tècnica següent

`BrokerageService` necessita un adaptador `IbkrBroker` darrere del mateix
contracte que Ostium: connexió a IB Gateway, contract qualification, mapping de
símbols, quotes, ordres bracket, fills, posicions, comissions, idempotència i
reconciliació després de reconnectar. Primer s'executa contra el compte paper
d'IBKR. TradingAgent continua sent l'únic responsable de senyal, admissió,
risc, compounding i circuits de seguretat.
