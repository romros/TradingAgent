# PEP → KO D1 trend pullback — rebutjada

La campanya va generar 60 candidats PEP train, en va congelar quatre de
famílies diferents i només `Strategy 0.242` va superar la validació PEP amb
costos d'estrès. A 1.000 USD va donar 25 operacions, +7,93%, PF 1,290 i DD
6,10% durant 2022–2023.

La mateixa estratègia, sense ajustar cap paràmetre, va produir 30 operacions
en KO. Una operació del 2022-11-30 entra i toca el profit target dins la
mateixa barra D1. Amb OHLC diari no es pot provar que l'entrada succeís abans
del target. El contracte preregistrat prohibia explícitament aquesta
ambigüitat, per tant la família queda rebutjada i no s'obre OOS 2024.

Evidència canònica:
`data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1/decision.json`.

No s'ha de rescatar canviant el target o acceptant retrospectivament barres
ambigües. Una campanya futura haurà d'utilitzar dades intradia o una sortida
exclusivament temporal preregistrada com una hipòtesi nova.
