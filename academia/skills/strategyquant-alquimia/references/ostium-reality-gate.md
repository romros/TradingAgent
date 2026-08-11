# Ostium reality gate

Aplicar aquest playbook al catàleg d'estratègies per a comptes de 200–500 USDC a
Ostium. L'objectiu de recerca és intentar 500→1.000 USDC aproximadament en dotze
mesos; és una meta per simular, no una promesa ni un criteri per relaxar gates.
Permetre entre una i sis estratègies netes dins EUR/USD, US500/USD i XAU/USD.
Preferir 3–6 només quan la diversificació millori mètriques fora de mostra després
de costos. Una sola família és admissible si compleix sola retorn, drawdown, règims,
concentració i economia real. No exigir una estratègia per cada actiu.

## Recuperar l'estat abans d'actuar

1. Llegir `academia/packages/strategyquant/ostium-500-objective.json`.
2. Llegir `academia/packages/strategyquant/ostium-500-strategy-catalog.json`.
3. Consultar `academia/experiments/failure-memory.json` i les observacions citades
   per l'actiu o família.
4. Executar `python3 academia/tools/ostium_objective_status.py`.
5. Formular la tasca amb `contribution`, `asset`, decisió esperada, stop condition
   i `uses_holdout=false`; rebutjar-la si no avança l'objectiu.

No confiar en recomptes memoritzats: el catàleg és l'estat viu. No repetir una
família amb un altre indicador, timeframe, direcció o leverage quan el mecanisme
ja està tancat.

## Ordre obligatori

1. **Causa i dada:** definir un mecanisme diferent i una regla falsable.
2. **Point-in-time:** provar quan cada valor era realment publicat, incloses
   revisions, exclusions i retard. Una dada associada a un mes no era
   necessàriament coneguda aquell mes.
3. **Cheap screen:** mesurar freqüència, moviment brut, simetria i estabilitat al
   train. Preregistrar regla, intents, costos, splits i stop abans de calcular.
4. **Economia Ostium:** usar spread, impacte, fee, oracle, rollover, nocional mínim,
   marge, leverage segur i liquidació del capital objectiu.
5. **SQ:** usar SQCLI/GUI només si els gates anteriors passen i SQ aporta generació,
   retest o robustesa que no es pot obtenir més barat.
6. **Validació:** obrir-la una vegada sense canviar la regla.
7. **Robustesa:** concentració anual/direccional, MAE, paràmetres, bootstrap o
   Monte Carlo proporcionals al risc de decisió.
8. **Holdout:** obrir només per finalistes preregistrats; una lectura el converteix
   en desenvolupament per a qualsevol iteració posterior.
9. **Transferència:** paritat d'ordres, paper trading i només després una decisió
   humana separada sobre live.

Aturar al primer gate fallit. Leverage redueix collateral; no converteix
expectativa negativa en edge.

Simular el target x2 quan existeixi almenys una família promocionable. Començar pel
conjunt més petit i afegir components, fins a sis, només si milloren probabilitat de
target, temps, drawdown, règims o concentració sense dependre del holdout. Variants
correlacionades de la mateixa família no compten automàticament com diversificació.
Limitar el risc simultani total al 3%, el drawdown al 15%, el leverage efectiu al
5x i la contribució de benefici d'un sol actiu al 50%.

## Dades externes i rols

Classificar cada variable abans del test:

- `ENTRY_TRIGGER`: disponible abans de l'entrada amb timestamp verificable.
- `RISK_OR_REGIME`: context conegut ex ante que modifica risc, no inventa senyal.
- `POST_HOC_CONTEXT`: explicació posterior; mai pot rescatar una estratègia.

Conservar vintages quan hi ha revisions. No substituir consens històric per una
predicció de model ni alinear dades retardades amb el període que descriuen.
Registrar l'absència de dades com a gate bloquejat, no com a zero ni com a rebuig
del mecanisme.

## Mesurar execució US500

Usar `@ostium/builder-sdk@0.7.0` o versió oficial auditada en `createReadOnly`, dins
un contenidor efímer. No usar signer, clau privada, transaccions ni servei
permanent.

Protocol congelat:

- timezone: `America/New_York`; calcular sempre la conversió local i DST;
- finestres: open `09:30–10:30`, midday `12:00–13:00`, close `15:00–16:00`;
- tres dies de mercat diferents;
- per cada dia i finestra: mínim 20 mostres vàlides i span mínim de 30 minuts;
- exigir `market_open=true` i bid ≤ mid ≤ ask;
- resumir mediana, p90, p95, màxim, slippage per costat/nocional, fees i rollover;
- no versionar JSONL brut: versionar agregat, timestamps, hash temporal i decisió.

Executar el capturador i el resum existents:

```bash
node academia/tools/collect_ostium_execution_quotes.mjs \
  --output=/tmp/spx-quotes.jsonl --window=open --count=20 --interval-ms=95000
python3 academia/tools/summarize_execution_quotes.py /tmp/spx-quotes.jsonl
```

No etiquetar overnight o after-hours com open/midday/close. Una finestra qualifica
individualment; el gate global només passa amb tres dies complets.

## Memòria i resposta

Després de cada decisió:

1. Desar una observació agregada amb font, timing, capital, costos, resultat i
   `do_not_repeat`.
2. Actualitzar el catàleg sense esborrar fracassos.
3. Afegir un manifest FTS quan l'insight sigui generalitzable.
4. Executar tests, validar JSON i `git diff --check`.
5. Fer commit petit només dels fitxers d'`academia/`; ignorar canvis paral·lels.

Comunicar sempre: objectiu, resultat net, decisió, què continua bloquejat, si cal
SQCLI i següent acció temporal concreta. Diferenciar `BLOCKED_DATA`, `REJECT`,
`CONTINUE_VALIDATION` i `PROMOTABLE`; zero candidats és un resultat honest.
