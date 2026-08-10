# Errata del model de costos d'Alquímia

## GBPUSD London-fix v26

L'artefacte v26 va congelar `opening_oracle_usdc=0.10` com a cost net per trade.
La documentació d'execució ja auditada indica que aquest import es reemborsa
després d'un tancament complet reeixit. Per tant, la frase que atribuïa el rebuig
principalment a l'oracle era incorrecta.

El veredicte quantitatiu **no canvia**: el millor punt sense cap fricció tenia PF
1,063 i +0,031 USDC/trade, mentre que amb els 8 bps base congelats tenia PF 0,21
i −0,78 USDC/trade. El cost percentual executable, no l'oracle reemborsable, és
el falsador suficient.

No es reescriu l'artefacte immutable ni la seva cadena. A partir de v27 el model
separa `oracle_locked_usdc` de `oracle_net_cost_usdc`: base i conservador assumeixen
reemborsament complet; l'estrès pot modelar una fallada de reemborsament.
