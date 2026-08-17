# Cinquena edge sobre marge residual — rebutjada

La família multi-actiu `SMA200 + tres baixades + hold 10` continua consolidada
com a edge de recerca. El que es rebutja és una política concreta per afegir-la
a la cartera 2x de quatre peces amb els mateixos 2.000 USD.

Política congelada: les quatre peces tenen prioritat; la candidata disposa de
tres slots de màxim 333,33 USD i una entrada es bloqueja si la caixa conjunta
baixaria de -2.000 USD. Costos: 1 USD per costat, 10 bps de slippage i 8%
d'interès sobre préstec incremental.

Resultat 2022–2024:

- retorn +63,00% i CAGR 17,70%, contra +56,04% i CAGR 16,00% de la base;
- drawdown 21,01%, contra 15,92% de la base;
- 130 trades, PF 1,285 i +203,76 USD tancats abans de finançament;
- 64,57 USD de finançament incremental;
- zero entrades bloquejades per marge, 12 inassequibles i tres obertes al final.

Decisió: `FAIL_FIFTH_EDGE_RESIDUAL_MARGIN`, perquè el gate congelat exigia DD
≤20%. No es redueix retrospectivament el cap de 333,33 USD per fabricar un
pass. La família es conserva; aquesta política d'agregació no.

Evidència: `data/ibkr_sq_v2/five_edge_residual_margin_v1/result.json` i
`lab/sq_bridge/five_edge_residual_margin_preregistration_v1.json`.
