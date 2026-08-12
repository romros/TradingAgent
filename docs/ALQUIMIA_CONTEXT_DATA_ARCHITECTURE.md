# Alquímia — arquitectura de context, notícies i models

## Principis

- El trading crític és local i determinista; cap API de model és al camí de TP/SL.
- Fonts oficials i dades de mercat tenen prioritat sobre xarxes socials.
- X serveix per descobrir canvis de narrativa o informació ràpida, no per validar
  tot sol una operació agressiva.
- Models analitzen; un agregador determinista decideix entre accions acotades.
- Tot replay utilitza només informació disponible en aquell moment.
- Proveïdors i models són adaptadors substituïbles, no dependències del domini.

## Components

```text
OfficialSource ─┐
News/RSS ───────┼→ collectors → raw append-only store → normalizer → event ledger
X API/Grok X ───┘                                      │
Market/Ostium ──────────────────────────────────────────┤
                                                       ↓
                                         point-in-time context snapshot
                                                       ↓
                       quantitative / macro / execution / devil-advocate agents
                                                       ↓
                                   deterministic quorum + veto policy
                                                       ↓
                     signed ContextDecision → TradingAgent state machine
```

### 1. Collectors

Adaptadors independents:

- `official_http`: Fed, BCE, BoJ, BLS, BEA, CFTC i calendaris oficials;
- `rss_news`: titulars i metadades de fonts amb llicència compatible;
- `x_api`: posts recents o arxiu complet quan hi hagi credencial i pressupost;
- `xai_search`: descoberta agentiva amb X Search i cites;
- `market_context`: OHLC, volatilitat, spread, slippage i estat d'Ostium.

Cap collector retorna una decisió de trading. Desa la resposta original, headers,
consulta, pàgina/paginació, timestamps, hash i error. Les claus només entren per
variables d'entorn o un secret manager; mai a Git, logs o receipts.

### 2. Raw store immutable

Contingut comprimit per hash, append-only. Cada captura registra:

- `source_id` i `source_tier`;
- URL o identificador del post;
- `published_at`: quan la font diu que es va publicar;
- `effective_at`: moment econòmic al qual correspon, si és diferent;
- `retrieved_at`: quan Alquímia ho va conèixer;
- `revised_at` i relació amb la versió anterior;
- hash SHA-256, MIME, idioma, llicència i collector/version.

Per evitar informació futura, un replay a les 14:00 només pot llegir registres
amb `retrieved_at <= 14:00`, encara que després descobrim una publicació anterior.

### 3. Event ledger normalitzat

Els parsers deterministes converteixen fonts a esdeveniments versionats:

```json
{
  "event_id": "...",
  "event_type": "US_CPI_RELEASE",
  "asset_tags": ["XAUUSD", "EURUSD", "US500"],
  "published_at": "...",
  "retrieved_at": "...",
  "values": {"actual": 3.5, "previous": 3.4},
  "source_refs": ["sha256:..."],
  "revision": 0
}
```

La sorpresa respecte al consens només s'afegeix si la font i timestamp del
consens són disponibles. Text, sentiment o causalitat generats per models van en
un camp d'anotacions; mai substitueixen els valors originals.

### 4. Snapshot point-in-time

Abans del consell, un constructor determinista crea un paquet immutable amb:

- estat quantitatiu dels mercats;
- esdeveniments coneguts i calendari pròxim;
- notícies/posts deduplicats i atribuïts;
- estat de costos i execució;
- estratègies i accions que es poden habilitar;
- `as_of`, caducitat i hashes de tots els inputs.

Aquest mateix snapshot es pot reproduir en backtest, paper i auditoria.

### 5. Proveïdors de models

Interfície única `ModelProvider.analyze(snapshot, role, schema)` amb adaptadors:

- `xai`: Grok i X Search;
- `openrouter`: selecció multi-model i fallback;
- `local`: model local futur;
- `fixture`: respostes deterministes per tests i replay.

Cada invocació registra model canònic, proveïdor real, versió de prompt, schema,
paràmetres, latència, tokens/cost, cites, resposta bruta, resposta validada i
hash. En recerca es pot usar temperatura baixa/seed, però una sortida repetible
no es pressuposa: la decisió agregada sí ha de ser reproduïble a partir de les
opinions desades.

OpenRouter només usarà models que suportin `structured_outputs`, amb schema
estricte i `require_parameters=true`. La política pot ordenar proveïdors,
permetre fallback i exigir zero data retention quan sigui disponible. Cap canvi
automàtic de model pot passar desapercebut: el model efectiu queda al ledger.

### 6. Consens i motor de risc

Les opinions passen validació JSON i cites. Un agregador sense LLM aplica quorum,
confiança mínima, caducitat, independència de fonts i vetos. El resultat només és
una acció de l'allowlist del consell de context. El motor de risc torna a limitar
mida, leverage, exposició i pèrdua, encara que el consell proposi risc agressiu.

## Jerarquia de confiança

1. Font oficial/primària amb timestamp i contingut capturat.
2. Dada de mercat o Ostium observada i hashada.
3. Mitjà atribuïble amb article original.
4. Compte X oficial o expert preregistrat.
5. Altres posts X: senyal de descoberta, no evidència suficient.
6. Resum d'un model sense cites verificables: no usable.

## Historial i replay

No reconstruirem el passat preguntant avui a un model “què se sabia llavors”.
Usarem, per ordre:

1. captures pròpies acumulades des d'ara;
2. arxius oficials amb hora de publicació i versions;
3. X full-archive, si el cost/accés ho justifica;
4. datasets de notícies amb llicència clara.

Els períodes sense evidència point-in-time queden marcats `CONTEXT_UNAVAILABLE`;
no s'omplen amb inferències. Primer validarem estratègies SQ sense consell i
després mesurarem el valor incremental del consell només en períodes coberts.

## Estructura de servei proposada

```text
packages/context/
  domain/          # Event, Snapshot, Opinion, ContextDecision
  collectors/      # official_http, rss, x_api, xai_search, market
  normalize/       # parsers deterministes per font
  storage/         # raw CAS, ledger i índex temporal
  providers/       # xai, openrouter, local, fixture
  council/         # rols, schemas, quorum i vetos
  replay/          # reconstrucció point-in-time
  api/             # read-only status; control autenticat en el futur
```

La primera implementació pot viure dins TradingAgent perquè consumeix decisions;
si madura, el contracte permet extreure-la com a servei sense canviar estratègies
ni motor de risc.

## Fases d'implementació

1. Schemas, fixture provider, raw store i ledger local; sense cap clau externa.
2. Collectors oficials i snapshot actual; replay determinista.
3. OpenRouter en mode recerca, sense autoritat operativa.
4. X API o Grok X Search amb allowlist de comptes/consultes i pressupost.
5. Consell en shadow mode comparat amb cartera determinista.
6. Paper ≤14 dies; live només amb autorització explícita.

No necessitem encara la clau d'OpenRouter. Es demanarà quan les fases 1–2 tinguin
tests i un snapshot reproduïble; així no gastarem tokens abans de tenir els gates.
