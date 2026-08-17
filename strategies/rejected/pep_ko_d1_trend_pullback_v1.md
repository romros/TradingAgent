# PEP → KO D1 trend pullback — rebutjada

La campanya va generar 60 candidats PEP train, en va congelar quatre de
famílies diferents i només `Strategy 0.242` va superar la validació PEP amb
costos d'estrès. A 1.000 USD va donar 25 operacions, +7,93%, PF 1,290 i DD
6,10% durant 2022–2023.

La mateixa estratègia, sense ajustar cap paràmetre, va produir 30 operacions
en KO. Una operació del 2022-11-30 entrava i tocava el profit target dins la
mateixa barra D1. La revisió posterior, permesa explícitament per la decisió
original, va usar els 390 minuts RTH congelats de Dukascopy: l'entrada és a
les 14:30 UTC i el target no s'observa fins a les 20:50 UTC. Per tant no hi ha
ambigüitat causal i es va poder obrir l'OOS 2024 sense canviar la regla.

L'OOS és el rebuig definitiu. KO completa 14 operacions però perd amb els tres
models de costos. En estrès retorna −6,72% amb 1.000 USD, −5,13% amb 2.000 i
−4,87% amb 3.000; els PF respectius són 0,650, 0,728 i 0,743. El win rate del
64,29% no compensa la mida de les pèrdues. Com que la preregistració exigia
retorn positiu per actiu, la família PEP→KO falla i no cal consumir l'OOS PEP.

Evidència canònica:

- `data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1/decision.json`
- `data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1/ko_intrabar_forensic_v1.json`
- `data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1/ko_oos_2024/0_242_v2/small_account_audit.json`

No s'ha de rescatar canviant target, stop, mida o filtre després de veure
l'OOS. Una campanya futura necessita un mecanisme materialment diferent i una
preregistració nova.
