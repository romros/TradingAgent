# Micromòdul: interpretar una Walk-Forward Matrix

Estat: mostra pedagògica `v0.1`; pendent de demo local a la build objectiu.

## Objectiu

En acabar, l'estudiant pot explicar què representa cada cel·la d'una WFM,
distingir estabilitat regional d'un pic aïllat i evitar interpretar un `pass` com
una garantia de rendibilitat.

## Prerequisits

- diferència entre in-sample i out-of-sample;
- paràmetres optimitzables d'una estratègia;
- lectura bàsica de drawdown, benefici i nombre de trades.

## 1. De WFO a WFM

**Fet documentat.** Una WFO optimitza en un segment passat i aplica els paràmetres
al segment OOS següent. Repeteix aquesta seqüència cronològicament.

**Fet documentat.** Una WFM executa múltiples WFO variant almenys el nombre de
runs i el percentatge OOS. Cada cel·la resumeix una combinació.

**Inferència.** Com que s'han provat moltes combinacions, escollir retrospectivament
el millor punt crea un problema de selecció. Una regió estable és més informativa
que un pic envoltat de fracassos, però tampoc és una prova de rendiment futur.

## 2. Lectura en cinc passos

1. Confirma quins paràmetres s'optimitzen i quants valors es proven.
2. Anota la graella de runs/OOS i el nombre total de cel·les.
3. Llegeix els criteris de `pass`; no assumeixis que els defaults són universals.
4. Busca zones veïnes consistents i inspecciona per què fallen les altres.
5. Revisa els runs: drawdown, trades, concentració de benefici i comparació amb
   l'estratègia original.

## 3. Exemple conceptual

Suposa una graella de 3 nombres de runs per 3 percentatges OOS. Una sola cel·la
excel·lent entre vuit resultats febles és fràgil. Sis o set cel·les properes amb
resultats acceptables suggereixen menor sensibilitat a aquella configuració. Això
només justifica una prova posterior; no autoritza desplegament ni trading.

## Errors habituals

- confondre WFO amb WFM;
- dir que OOS no s'ha mirat quan s'han comparat moltes cel·les i llindars;
- seleccionar només benefici net;
- ignorar runs sense prou trades o amb benefici concentrat;
- copiar un llindar 3×3 de l'exemple oficial com si fos una llei estadística;
- marcar el resultat `verified` sense conservar configuració, build i artifacts.

## Exercici

Una matriu 3×3 té set cel·les que passen. Sis formen un bloc; la setena, que té el
benefici màxim, queda aïllada. El bloc té drawdown moderat i la cel·la aïllada
concentra el 70% del benefici en un sol run.

Respon:

1. Quina zona triaries per investigar i per què?
2. Quines dades falten abans de considerar el resultat robust?
3. Quin estat d'evidència assignaries abans d'executar una reproducció local?

## Criteri de correcció

Resposta satisfactòria: prioritza el bloc, no promet rendibilitat, assenyala la
concentració i demana paràmetres, períodes, costos, nombre de trades, criteris de
pass, build i intents. L'estat màxim és `corroborated`; sense prova local no és
`tested` ni `verified`.

## Fonts

- `sq_official_walk_forward_optimization_20150506`
- `sq_official_walk_forward_matrix_20150506`
- `sq_official_walk_forward_values_20190101`
