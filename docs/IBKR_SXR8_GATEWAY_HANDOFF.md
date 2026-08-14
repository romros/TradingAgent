# Desbloqueig paper de SXR8

L'estratègia i el contracte públic estan verificats, però cap ordre està
autoritzada. El Client Portal Gateway paper ha d'estar escoltant localment a
`https://localhost:5000` i la sessió s'ha d'autenticar manualment.

Quan estigui autenticat, executar:

```bash
bash scripts/ibkr/verify-sxr8-paper-readiness.sh
```

El procés només fa GET sobre tres endpoints allowlisted. No conté cap endpoint
d'ordre. L'artefacte final és
`data/ibkr_sq_v2/turn_of_month/sxr8_paper_readiness.json`.

Per arribar a `PAPER_READY` encara cal que l'evidència del compte confirmi:

1. autenticació i connexió;
2. `conid=75776072`, ISIN `IE00B5BMR087`, EUR i IBIS2;
3. comissió observada del compte paper;
4. sizing executable amb fraccions o accions senceres.

El punt 2 el pot comprovar la sonda actual. Els punts 3 i 4 requereixen una
extensió read-only basada en informació del compte o una previsualització de
comissió que no transmeti l'ordre; fins llavors el gate falla tancat.

## Alternativa sense donar-se d'alta

SXR8 està `SHADOW_PAPER_READY` sense compte ni broker. El gate és
`data/ibkr_sq_v2/turn_of_month/sxr8_shadow_readiness.json`.

- Calendari oficial Xetra 2026: 254 sessions i 22 accions mensuals.
- Proper cicle: BUY hipotètic 31-08-2026, SELL hipotètic 04-09-2026.
- Runner diari: `python3 apps/sxr8_shadow_daily.py --capital 1000`.
- En dies sense acció no fa cap petició de xarxa.
- En dies d'acció obté un preu de referència públic, calcula accions senceres
  i escriu `data/shadow/sxr8_turn_of_month.json`.
- Cada registre és `HYPOTHETICAL_NOT_SENT`; el runner no importa cap client
  IBKR i no té capacitat de transmetre ordres.
