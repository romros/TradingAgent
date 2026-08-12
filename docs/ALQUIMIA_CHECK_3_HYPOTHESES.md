# CHECK 3 — hipòtesis oportunistes abans de performance

**Estat:** `PASS_PREPERFORMANCE_HYPOTHESIS_CATALOG`

**Contracte canònic:**
[`noncrypto_playbook_hypotheses_v5.json`](../lab/sq_bridge/noncrypto_playbook_hypotheses_v5.json)

Aquest catàleg s'ha escrit sense llegir PnL, holdout ni candidats antics. Són
sis preguntes que sotmetrem a prova, no sis estratègies aprovades.

## Ordre teòric inicial

### 1. XAUUSD M15 — ruptura de compressió amb catalitzador macro

**Idea:** abans d'una dada programada, l'or es comprimeix; després només s'entra
si el preu trenca el canal i el spread torna dins del límit.

**Exemple:** IPC a les 14:30; les barres anteriors tenen rang baix. Una barra M15
tanca per sobre del canal. Entrada a l'obertura següent, SL a l'altre costat/ATR,
TP en múltiples de risc i sortida obligatòria entre 1 i 4 hores.

**Per què podria funcionar:** les notícies macro afecten preus FX en finestres
curtes, i l'or del 2026 combina demanda estructural amb canvis bruscos de
sentiment. **Per què podria fallar:** slippage de notícia, ruptura falsa o notícia
ja descomptada. Prior teòric: **alt, però amb cost d'esdeveniment dur**.

### 2. XAUUSD M15 — reversió d'un xoc que falla

**Idea:** un moviment anormal travessa un extrem però torna a tancar dins del
rang. Només s'opera contra el xoc si el consell classifica el règim com a rang o
esgotament, no com una revaloració macro persistent.

**Exemple:** caiguda de diverses ATR, recuperació del rang anterior, entrada long
a la barra següent, SL sota l'extrem, objectiu al punt mitjà/pre-xoc i màxim
d'1–5 hores.

**Valor per a la cartera:** complementa la primera; una busca continuació i
l'altra un fracàs. Mai poden quedar armades simultàniament sobre el mateix xoc.
Prior: **alt**, perquè el 2026 l'or ha mostrat tant impulsos com correccions grans.

### 3. USDJPY M15 — ruptura del rang asiàtic a Londres

**Idea:** definir el rang asiàtic complet i operar una ruptura durant la transició
a Londres només si el rang és compacte i la tendència curta acompanya.

**Exemple:** rang de 35 pips, ruptura confirmada per tancament M15, entrada a la
barra següent, SL dins/darrere del rang, TP per projecció i màxim d'1–4 hores.

**Per què ara és rellevant:** el diferencial monetari EUA–Japó està canviant;
això pot crear moviments, però també fa invàlid assumir el vell règim de tipus
japonesos gairebé zero. Prior: **mitjà-alt**.

### 4. USDJPY M15 — reversió d'una ruptura de sessió fallida

**Idea:** si la ruptura anterior torna ràpidament dins del rang en un règim
lateral, operar cap al centre. Es desactiva davant decisions Fed/BoJ o tendència.

**Exemple:** falsa ruptura del màxim asiàtic, tancament de nou dins, short a la
barra següent, SL sobre el fals extrem i sortida al centre abans de tres hores.

**Valor:** cobreix dies laterals on el breakout perd. Prior: **mitjà**; el marge
fins al centre pot ser massa petit després de costos.

### 5. US500 D1 — rebot després de xoc de volatilitat

**Idea:** després d'una caiguda diària anormal, comprar només si el tancament
recupera part del rang i la volatilitat deixa d'accelerar.

**Exemple:** gran selloff, tancament lluny del mínim, entrada a la sessió següent,
SL sota el mínim amb estrès de gap, TP curt i màxim d'1–5 sessions.

**Valor:** diversifica FX/or. Prior: **mitjà**, perquè D1 té menys oportunitats i
els gaps poden ser perillosos en un compte de 200 USDC.

### 6. EURUSD D1 — tendència curta després de breakout

**Idea:** ruptura diària amb retorn curt alineat, mantinguda 2–10 dies, sempre que
el context Fed/BCE no contradigui la direcció i el rollover no domini.

**Valor:** es basa en l'evidència general de time-series momentum i en la millor
font històrica del nostre univers. Prior: **mitjà-baix per al perfil oportunista**,
perquè és més lenta; es conserva com a diversificador, no com a motor diari.

## Què aporta la literatura i què no

- Moskowitz, Ooi i Pedersen documenten persistència temporal en índexs, divises
  i commodities, però en horitzons més llargs que alguns dels nostres trades.
  Justifica preguntar, no copiar paràmetres:
  https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- La literatura d'opening-range breakout troba efectes intradia en futurs, però
  altres mercats, períodes i costos no són Ostium; cal falsificació pròpia:
  https://doi.org/10.1109/ACCESS.2019.2899177
- Moreira i Muir mostren que reduir exposició quan la volatilitat puja pot
  millorar risc/retorn. Ho usem com a principi de sizing, no com a senyal copiat:
  https://www.nber.org/papers/w22208
- La recerca d'anuncis macro troba reaccions FX fortes especialment en els
  primers minuts; això reforça el veto per spread/slippage i la necessitat de
  timestamps exactes:
  https://www.cambridge.org/core/services/aop-cambridge-core/content/view/CE5AB6783BC3486CD07ACF242A73FBB8/S0022109000000995a.pdf/effects_of_macroeconomic_news_on_high_frequency_exchange_rate_behavior.pdf

## Vigència al 11/08/2026

- La Fed manté 3,50–3,75%, descriu inflació elevada i té dissidents partidaris
  d'apujar: USD, US500 i XAU poden reaccionar fort a noves dades.
- El BCE manté tipus i decideix reunió a reunió: no pressuposem una direcció fixa
  per EURUSD.
- El BoJ continua normalitzant des de nivells encara baixos: USDJPY necessita
  classificació de règim, no un biaix permanent long.
- L'or conserva demanda estructural de bancs centrals però ha tingut impulsos i
  correccions molt grans: té sentit provar tant breakout com failed-shock.

Aquestes observacions només defineixen contextos i vetos. No s'utilitzaran per
retocar una regla després de veure el seu PnL.

## Invariants comuns abans del Check 4

- Senyal al tancament i entrada a l'obertura següent.
- Cada trade neix amb TP, SL i temps màxim.
- L'SL només es pot acostar.
- Baseline sense gestor ràpid per mesurar si el trailing aporta valor real.
- Moviment brut esperat almenys 3× el cost p95 provisional.
- Màxim tres paràmetres sensibles per playbook.
- Leverage només després d'haver validat l'avantatge a 1×.
- Cap quota d'operacions o benefici diari; sense oportunitat, `WAIT`.

## Decisió proposada

Portar les sis hipòtesis al Check 4, però amb pressupost desigual: més intents a
XAU breakout/reversion i USDJPY breakout; menys a USDJPY reversion, US500 i
EURUSD. El pressupost exacte, rangs i holdout es congelaran al preregistre abans
de consultar performance.
