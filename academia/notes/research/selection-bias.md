# Contrast metodològic — selecció i backtest overfitting

La documentació de StrategyQuant explica com executar robustness tests. White
(2000) i Bailey & López de Prado (2014) afegeixen una limitació que la interfície
no pot resoldre sola: el resultat s'ha d'interpretar segons tota la cerca que l'ha
produït.

## Insight operacional

El comptador rellevant no és només el nombre d'estratègies finals. Inclou variants
de regles, paràmetres, filtres, runs/OOS, mètriques i canvis decidits després de
mirar resultats. Per això qualsevol campanya ha de declarar `attempt_budget` i
registrar `attempts_observed`.

Un holdout deixa de ser cec quan influeix en una decisió. `holdout_peeks` ha de ser
zero per al gate final. Si es consulta i després es continua desenvolupant, cal
reetiquetar-lo com a dades de desenvolupament i reservar un nou holdout.

## Conseqüència per a l'agent

L'agent no promocionarà automàticament una claim perquè una estratègia passi WFM.
Primer exigirà pressupost/intents, costos, protocol congelat i holdout intacte.
DSR o Reality Check són candidats a experiments posteriors, no dependències actuals.
