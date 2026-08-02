# Nota de síntesi — Walk-Forward Matrix

Estat: `corroborated`, no `verified`. Les fonts oficials són antigues i encara no
hi ha una execució local sobre la build objectiu.

## Model mental

Una Walk-Forward Optimization (WFO) prova un calendari concret de reoptimització.
La Walk-Forward Matrix (WFM) repeteix aquesta WFO sobre una graella de nombres de
runs i percentatges OOS. Per tant, una cel·la no és una estratègia diferent: és el
resultat d'un calendari/configuració de reoptimització diferent.

## Què permet observar

- sensibilitat als runs i al percentatge OOS;
- estabilitat regional: zones veïnes amb comportament semblant;
- concentració del resultat en pocs runs;
- si la reoptimització supera o empitjora la configuració original sota les
  mètriques seleccionades.

## Què no demostra

- rendibilitat futura;
- absència de curve fitting;
- validesa dels llindars triats;
- independència estadística entre cel·les;
- que el millor punt de la graella sigui un calendari òptim fora de mostra.

Buscar el màxim aïllat torna a introduir selecció sobre moltes variants. La lectura
pedagògica prudent és preferir regions estables, inspeccionar també els fracassos i
registrar quantes combinacions s'han provat.

## Evidències

- `sq_official_walk_forward_optimization_20150506#section:definition`
- `sq_official_walk_forward_matrix_20150506#section:definition`
- `sq_official_walk_forward_matrix_20150506#section:interpretation`
- `sq_official_walk_forward_values_20190101#section:special-values`

## Pendent d'experiment

Repetir una matriu petita en la build objectiu amb un projecte educatiu, conservar
configuració/hash i comprovar noms de camps, defaults, criteris de pass/fail i cost.
No reutilitzar estratègies ni resultats de campanyes de trading.
