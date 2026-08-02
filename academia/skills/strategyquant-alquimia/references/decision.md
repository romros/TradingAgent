# Revisió de candidats

Entrada mínima: `id`, `trades`, `minimum_trades`, `costs_included`,
`attempt_budget`, `attempts_observed`, `holdout_peeks`, `wfm_passed_cells`,
`wfm_total_cells`, `wfm_largest_connected_region`, `max_run_profit_share` i
`drawdown_acceptable`.

**Descartar** si el holdout està contaminat, se supera el pressupost, falten costos,
cap WFM passa o el drawdown viola el límit. No salvar amb més cerca.

**Prova dirigida** si falten trades, només hi ha pics o més del 50% del benefici
depèn d'un run. Proposar una prova que resolgui aquest dubte.

**Continuar** si supera mínims, respecta pressupost/holdout, mostra estabilitat i no
concentra resultat. Significa autoritzar el següent test, mai live trading.

Els llindars són defaults modificables abans de la campanya, no constants universals.
