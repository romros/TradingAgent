# Wolfpack

Motor d'intel·ligència de mercat per convertir dades de venues, comportament de
traders i règims en situacions explicables. És un projecte separat dins
`academia/`: reutilitza evidència i política, però no executa trading ni modifica
StrategyQuant.

## Objectiu

Trobar informació que millori prospectivament decisions per a un compte de 500
USDC a Ostium. Una wallet guanyadora és una font potencial, no una estratègia.

L'univers d'observació és obert: cripto, divises, índexs, matèries primeres i
qualsevol venue amb dades auditables poden aportar edge. Cada mercat conserva
els seus propis gates de contracte, costos, liquiditat, latència i execució;
observar-ho tot no significa que tot sigui copiable ni operable a Ostium.

Hi ha dues vies de validació: consens de dues o més wallets, o una sola wallet
excepcional. La segona exigeix com a mínim 30 tancaments prospectius copiats,
PnL net després del retard i costos reals, profit factor ≥1,5, les dues meitats
positives, drawdown ≤15%, cap liquidació i profit no concentrat en una operació.
També exigeix latència mediana d'entrada ≤120 segons i shortfall d'implementació
medià ≤10 bps. Aquest shortfall compara el retorn del compte font amb el retorn
executable als bid/ask observats quan detectem l'obertura i el tancament.
Per tant, una font extraordinària pot ser suficient, però una bona ratxa no.

El roster té dues fases. `CANDIDATE` requereix almenys 10 tancaments copiats,
profit factor ≥1,2, ambdues meitats positives i els mateixos límits de latència
i shortfall; només continua en paper. `TITULAR` exigeix el filtre excepcional
complet de 30 tancaments i és l'únic estat elegible per a una futura cartera.
Ser titular no autoritza trading ni assigna capital: això requereix un gate de
cartera separat i permís explícit.

## Senyal global i risc agressiu

`portfolio_signal.py` exigeix almenys dos titulars amb consens ponderat del 67%,
tres revisions de model unànimes i un reward/risk net mínim d'1,5. La confiança
obre una escala paper d'1%, 2% o 3% de risc; no fixa directament el leverage.
Primer calcula la pèrdua fins a invalidació més costos d'estrès i després deriva
el nocional i el leverage, limitat a 5x, al màxim segur de liquidació i al màxim
del venue. Tota sortida conserva `live_trading_authorized=false`.

Wolfpack és el pla de control i evidència dins `academia/`, no un segon broker.
Si algun dia se n'autoritza l'execució, haurà de passar per un adaptador estret
cap al broker Ostium existent; Wolfpack no guardarà claus, signarà transaccions
ni duplicarà la lògica d'execució.

Els avisos són `WATCH`, `PAPER`, `CANDIDATE` i `AUTHORIZED`. El brief factual
actual només pot emetre `WATCH`; els nivells superiors necessiten els gates que
descriu `council.json`, i `AUTHORIZED` sempre requereix permís explícit.

## Flux

```text
diari de venues + fills públics + règim
                 ↓
           fets normalitzats
                 ↓
   Caçador → Fiscal → Gestor de risc
                 ↓
C0 dada / C1 anomalia / C2 hipòtesi / C3 paper
```

`C4 candidat operable` i `C5 autoritzat` no es poden generar fins que una versió
futura incorpori els gates prospectius i una autorització explícita. La versió
actual té sostre `C1` sense mostra i `C2` amb una cohort suficient; mai recomana
una entrada real.

## Ús

```bash
python3 academia/projects/wolfpack/wolfpack.py brief \
  --diary /tmp/cross-venue-diary-forward-20260813.jsonl \
  --follows /tmp/ostium-follow-forward-20260813.jsonl \
  --output /tmp/wolfpack-brief.json
```

Les adreces i feeds crus no entren a Git. `pack.json` només conté hashes, estat i
competència demostrada. Els briefs diaris agregats es podran promocionar a
`academia/experiments/observations/` quan compleixin el protocol.

El mantenidor finit escriu un checkpoint diari i comprova l'antiguitat del diari
i del heartbeat del follower. Els checkpoints continuen a `/tmp` fins a la revisió:

```bash
python3 academia/projects/wolfpack/maintain.py --days 30 \
  --diary /tmp/cross-venue-diary-forward-20260813.jsonl \
  --follows /tmp/ostium-follow-forward-20260813.jsonl \
  --heartbeat /tmp/ostium-follow-heartbeat-20260813.json \
  --output-dir /tmp/wolfpack-checkpoints
```

Recuperació humana: dir «revisa Wolfpack» o llegir
`/tmp/wolfpack-checkpoints/latest.json`. El procés no pot iniciar una conversa ni
enviar notificacions pel seu compte. És temporal i no té supervisor de reinici:
després d'un reboot cal rellançar els dos monitors i el mantenidor des de l'últim
timestamp conservat; no assumir que una absència de senyals és cobertura sana.

El shadow paper follower reprodueix només fills que tinguin bid/ask observables
en el moment de detecció. Usa 500 USDC, màxim 50 USDC de col·lateral per posició,
300 USDC simultanis i leverage màxim 5x. No completa el PnL net d'una operació
que travessa de dia fins que el contracte de rollover estigui reconciliat:

```bash
python3 academia/projects/wolfpack/paper_follow.py \
  --follows /tmp/ostium-follow-forward-20260813.jsonl \
  --output /tmp/wolfpack-paper.json \
  --duration-hours 720 --interval-seconds 900
```

El dashboard local consulta els feeds a cada petició i el navegador refresca la
vista cada 60 segons. La pestanya `Monitorització` resumeix BTC, LINK, US500,
XAU i EURUSD; la revisió factual té cadència de 10 minuts i el setup LINK manté
la seva captura d'un minut. `api/paper.csv` exporta el llibre paper auditable.
Les targetes de mostra porten `SIMULATION`; els avisos
derivats de dades reals indiquen si encara són `LIVE` o ja han expirat:

```bash
python3 academia/projects/wolfpack/dashboard.py --port 8787 --duration-hours 720 \
  --follows /tmp/ostium-follow-forward-20260813.jsonl \
  --heartbeat /tmp/ostium-follow-heartbeat-20260813.json \
  --paper /tmp/wolfpack-paper-forward-20260813.json \
  --checkpoint /tmp/wolfpack-checkpoints/latest.json
```

Per defecte escolta només a `127.0.0.1`. Des d'un altre ordinador cal un túnel
SSH; no s'ha d'exposar el port públicament sense autenticació.

La revisió Codex és finita, en sandbox de només lectura i dirigida per events.
Estableix una línia base i només invoca el model si canvia l'estat de LINK o el
règim d'una hora travessa els llindars congelats de BTC, US500, XAU o EURUSD:

```bash
python3 academia/projects/wolfpack/opportunity_codex_monitor.py \
  --diary /tmp/cross-venue-diary-forward-20260813.jsonl \
  --link-watch /tmp/link-watch-state.json \
  --output /tmp/opportunity-codex-review.json --interval-seconds 600
```

El snapshot inclou l'instrument, els dos setups preregistrats, confirmacions,
expiració, mida paper, invalidacions, objectius i causes de cancel·lació, fins i
tot abans que existeixi una posició. La sortida estructurada mai pot posar
`live_trading_authorized=true`. Codex
aporta judici crític; no substitueix els gates deterministes ni envia ordres.

Els setups paper independents tancats es reconcilien a
`academia/experiments/observations/` i el dashboard els suma una sola vegada a
l'equity combinada. Si falta una taxa contemporània, la vista diu `estimada`, el
CSV conserva `cost_complete=false` i el resultat no compta com edge demostrat.

`paper_ledger.py` fusiona cada font per identitat estable, sense convertir els
setups independents en trades de llops ni duplicar resultats. Manté JSON i CSV
efímers actualitzats per al dashboard:

```bash
python3 academia/projects/wolfpack/paper_ledger.py \
  --wolfpack /tmp/wolfpack-paper-forward-20260813.json \
  --standalone-dir academia/experiments/observations \
  --output /tmp/wolfpack-unified-ledger.json \
  --csv /tmp/wolfpack-unified-ledger.csv
```

La rèplica LINK v40 conserva la geometria percentual de v39 sobre un anchor
prospectiu nou. No canvia distàncies després del guany i captura el contracte,
fees i rollover a entrada i sortida. El gate continua exigint 10 tancaments;
una segona victòria tampoc demostraria edge per si sola.

## Manteniment

- diàriament: generar brief i comprovar fonts/errors;
- setmanalment: descobrir candidats amb dades passades, sense alterar la cohort
  congelada de l'experiment actiu;
- cada 30 dies: degradar/promoure per regla preregistrada i comparar contra
  baselines sense llops;
- cada canvi de font: revalidar contracte, escala, oracle, fees i timestamps.

No cal un LLM per mantenir la capa factual. Quan s'afegeixi un consell d'IA,
rebrà un brief immutable i haurà de retornar els contractes de `council.json`;
cap model podrà modificar mètriques o saltar el sostre de criticitat.
