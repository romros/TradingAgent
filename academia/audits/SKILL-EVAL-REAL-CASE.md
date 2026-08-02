# Avaluació de la skill — cas EURUSD H4

Entrada observada: temporal amb 138 trades, PF 1,25, R expectancy 0,13, DD
11,55% i pass; cost base 4,5 bps + 0,10 USDC, PF 0,51, expectativa -0,144
USDC i Monte Carlo rendible en 0,2% de runs.

Resposta produïda pel workflow:

```text
DECISIÓ: DESCARTAR
MOTIU: passa temporal, però l'edge desapareix amb els costos base.
RISC PRINCIPAL: economia bruta per trade insuficient per al compte petit.
SEGÜENT PAS: canviar font d'edge o fricció; no afinar paràmetres.
EVIDÈNCIA: alquimia-eurusd-h4-2026-08 / TEMPORAL_PASS_COST_FAIL
```

Checks: no recomana leverage ni WFM més gran; no confon OOS amb viabilitat;
proposa una direcció única i cita l'observació. **PASS** per aquest cas.

Límit: avaluació local amb resposta esperada explícita, no forward-test independent.
