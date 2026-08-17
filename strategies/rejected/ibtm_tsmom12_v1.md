# IBTM TSMOM12 — rebutjada

Transferència exacta, sense optimització, de la regla mensual TSMOM12 usada en
bons de durada més llarga. A inici de mes només manté IBTM si el darrer final
de mes supera el final del mateix mes de l'any anterior; altrament queda en
cash.

Train 2010–2021 és positiu (+10,47%), però validació 2022–2023 és −0,44%.
L'OOS 2024 recupera +3,19%, insuficient per rescatar el gate: validació+OOS
dona +2,74%, Sharpe anualitzat 0,229 contra el mínim congelat de 0,40 i només
13 mesos invertits. Decisió: **rebutjada**, sense provar venciments o lookbacks
alternatius després de veure el resultat.

Evidència: `data/ibkr_sq_v2/ibtm_tsmom12_v1/screen.json`.
