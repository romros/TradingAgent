# Cartera shadow SXR8 + CAT + MSFT + NFLX + JPM + SGLN — estat i continuïtat

> La millor cartera teòrica actual és CAT/MSFT/JPM/SGLN/NFLX i es documenta a
> `docs/BUY_HOLD_OBJECTIVE_STATUS.md`. El runner ja cobreix totes cinc peces de
> la candidata i conserva SXR8 com a diagnòstic addicional.

## Què és

És observació forward sense broker. El sistema consulta dades actuals, calcula
què haurien fet sis estratègies i desa intents hipotètics. **No envia ordres,
no està connectat a IBKR i no està autoritzat per paper broker ni live.**

Estratègies:

1. `SXR8 turn-of-month`: compra hipotètica l'última sessió Xetra del mes i
   venda hipotètica a l'open de la quarta sessió següent. Estat
   `SHADOW_PAPER_READY`.
2. `CAT 0.168`: entrada long quan baixa la pressió venedora `-DI(40)`, amb
   stop `2,5 × ATR(30)` i target `2,1 × ATR(30)`. Estat `RESEARCH_SHADOW`;
   conserva el bloqueig de 21/60 trades OOS.
3. `MSFT capitulation_d1`: després d'una caiguda extrema sota Bollinger,
   compra hipotèticament a l'obertura següent i ven al mateix tancament. Les
   dues potes es desen juntes de forma atòmica. Estat `RESEARCH_SHADOW`.
4. `NFLX 0.4681`: buy stop de breakout, SL `2,5 × ATR(15)` i TP
   `2,8 × ATR(15)`, exposició diagnòstica del 75% sense leverage. Estat
   `VALIDATED_RESEARCH_SHADOW`; no està autoritzada per broker.
5. `JPM Momentum60`: al primer open del mes entra si el tancament anterior és
   superior al de 60 sessions abans, i surt a l'open després de 20 sessions.
   Estat `ADMITTED_RESEARCH_SHADOW`, butxaca diagnòstica de 500 USD.
6. `SGLN TSMOM12`: compara l'últim tancament mensual amb el del mateix mes de
   l'any anterior. Converteix GBp→GBP→USD amb GBP/USD observat i costos d'estrès.
   Estat `CAPPED_RESEARCH_SHADOW`, butxaca màxima de 500 USD.

## Estat verificat el 2026-08-14

- Cartera de recerca 2022–2024: +16,72%, PF 1,203, drawdown tancat 9,76%.
- Correlació mensual: 0,321.
- CAT forward: 124 sessions, última 2026-08-13, pipeline `PASS`, acció `NONE`.
- SXR8: pròxima acció coneguda `BUY` el 2026-08-31.
- Posicions shadow actuals: SXR8 0, CAT 0, MSFT 0.
- Ordres enviades: 0.

## Panell nou i scheduler horari

```bash
python3 apps/shadow_control_panel.py --host 127.0.0.1 --port 8770 --interval 3600
```

Obrir: `http://127.0.0.1:8770`.

Per deixar-lo persistent després de reiniciar la màquina, la unitat versionada
és `deploy/systemd/tradingagent-shadow-panel.service`. S'executa com a servei
d'usuari, es reinicia si falla i continua mantenint l'aïllament de broker.

Execució manual exclusiva del carril NFLX, si mai cal diagnosticar-lo:

```bash
python3 apps/nflx_shadow_pipeline.py --capital 3000
```

La pestanya `Actius i selecció` reprodueix les lectures essencials d'un report
SQ: equity neta normalitzada, benchmark buy-and-hold, underwater/drawdown,
operacions, profit factor i motiu d'inclusió. La comparació comuna és 2022–2024;
l'històric llarg de MSFT apareix separat per no barrejar finestres.

La pestanya `NFLX 0.4681` mostra en llenguatge directe la regla, pipeline,
última sessió, buy stop pendent, posició/SL/TP hipotètics i els KPIs validats.
El feed és D1 ajustat per splits i exclou el dia actual fins després de les
16:15 de Nova York. El primer cicle només inicialitza estat per a la sessió
següent: no crea operacions shadow retroactives.

Diagnòstic de capital compartit 2022–2024 (pesos màxims fixos, sense
reutilització retrospectiva): 36,98% de capital mitjà desplegat, 80% màxim i
119 de 775 sessions amb dues estratègies coincidents. Temps exposat: SXR8
22,85%, CAT 70,92% i MSFT 1,99%. Per tant, els pesos són límits d'ús quan hi ha
senyal, no capital que hagi de quedar permanentment reservat. La mètrica
`retorn / fracció exposada` és eficiència descriptiva, no retorn anualitzat.

El procés fa un cicle immediat i un altre cada hora. CAT i MSFT actualitzen feeds,
verifiquen hash/antiguitat/warm-up i escanegen l'última sessió completa. SXR8 no
accedeix a xarxa si el dia no té una acció planificada. Tots dos són
idempotents. Si el procés es reinicia, els ledgers impedeixen duplicats.

Estat del scheduler:

- `data/shadow/hourly_scheduler_status.json`
- `data/shadow/cat_0168_pipeline_status.json`
- `data/shadow/msft_capitulation_pipeline_status.json`
- `data/shadow/nflx_04681_pipeline_status.json`
- `data/shadow/jpm_momentum60_pipeline_status.json`
- `data/shadow/sgln_tsmom12_pipeline_status.json`

## Registre shadow: JSON i CSV

Cada estratègia manté dos formats sincronitzats atòmicament:

- `data/shadow/cat_0168.json`
- `data/shadow/cat_0168.csv`
- `data/shadow/sxr8_turn_of_month.json`
- `data/shadow/sxr8_turn_of_month.csv`
- `data/shadow/msft_capitulation.json`
- `data/shadow/msft_capitulation.csv`
- `data/shadow/nflx_04681.json`
- `data/shadow/nflx_04681.csv`
- `data/shadow/nflx_04681_state.json`
- `data/shadow/jpm_momentum60.json`
- `data/shadow/jpm_momentum60.csv`
- `data/shadow/jpm_momentum60_state.json`
- `data/shadow/sgln_tsmom12.json`
- `data/shadow/sgln_tsmom12.csv`
- `data/shadow/sgln_tsmom12_state.json`

JSON és la font operativa. CSV és el mirall per inspecció humana, Excel o
DuckDB. Columnes: clau idempotent, estratègia, símbol, acció, sessió, preu de
referència, quantitat, nocional, comissió, estat, stop, target, tipus de sortida
i metadades JSON. Un CSV només amb capçalera significa que encara no hi ha cap
operació hipotètica.

Exemple DuckDB:

```sql
SELECT * FROM read_csv_auto('data/shadow/cat_0168.csv');
```

## Fitxers que una sessió nova ha de llegir primer

1. `docs/SHADOW_PORTFOLIO_RUNBOOK.md`
2. `docs/STRATEGY_LIBRARY.md`
3. `data/ibkr_sq_v2/two_strategy_portfolio/sxr8_cat_v1.json`
4. `data/shadow/hourly_scheduler_status.json`
5. Els quatre ledgers JSON/CSV.

No s'ha de modificar la regla CAT ni SXR8 amb dades forward. El 2025+ no es
pot reutilitzar com a train. Qualsevol `BUY/SELL` continua sent hipotètic fins
que l'usuari autoritzi explícitament un futur pas a paper broker.

MSFT ja està integrat al scheduler, però això no el converteix en una estratègia
aprovada per broker: continua sent recerca shadow i el període 2024–2026 ja és
monitoratge consumit, no un holdout verge. No es poden retocar els paràmetres
amb aquestes observacions.
