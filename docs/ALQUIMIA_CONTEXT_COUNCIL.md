# Alquímia — consell agentiu de context

Persistència, fonts, replay point-in-time i adaptadors de models es defineixen a
[`ALQUIMIA_CONTEXT_DATA_ARCHITECTURE.md`](ALQUIMIA_CONTEXT_DATA_ARCHITECTURE.md).

## Propòsit

Separar dues responsabilitats:

1. **Estratègies deterministes SQ/Python:** produeixen senyal, entrada, stop,
   objectiu i caducitat amb dades i regles exactes.
2. **Consell agentiu de context:** interpreta règim, calendari i notícies actuals
   i selecciona només accions prèviament autoritzades.

El consell no crea trades discrecionals ni reescriu una estratègia en calent.
Qualsevol decisió final es materialitza en un contracte estructurat, auditable i
validat determinísticament abans d'arribar al motor de risc.

El sistema revisa context i oportunitats cada dia, però no té quota diària de
trades ni de benefici. Si cap estratègia validada ofereix avantatge net, conserva
`WAIT`. L'absència de trade no permet relaxar consens, costos o senyals.

## Biblioteca de playbooks SQ

Cada estratègia promocionada es publica com un playbook immutable:

```text
playbook_id + versió
mercat/timeframe/direcció
contextos compatibles i incompatibles
finestra horària
regla d'entrada determinista
TP + SL + max_time
gestor ràpid autoritzat
cost màxim i règim de risc validats
hash de SQ, Python i evidència de paritat
```

El consell només arma playbooks complets. Si dos competeixen pel mateix risc, un
selector determinista de cartera aplica prioritat preregistrada, correlació i
exposició; mai fusiona fragments de dues estratègies durant l'execució.

## Què pot decidir

Per cada estratègia validada, el consell pot escollir:

- `DISABLED`: no permetre noves entrades;
- `ENABLED_REDUCED`: risc reduït;
- `ENABLED_NORMAL`: risc normal del tram de capital;
- `ENABLED_AGGRESSIVE`: només en el tram 200→500 i si la política ho autoritza;
- horitzó prevalidat, per exemple `INTRADAY`, `24H` o `48H`;
- biaix prevalidat `LONG_ONLY`, `SHORT_ONLY` o `BOTH`;
- caducitat de la decisió i moment obligatori de revisió.

No pot:

- inventar un preu d'entrada, stop o take-profit;
- ampliar un stop després d'entrar;
- superar leverage, risc simultani o pèrdua diària autoritzats;
- operar un mercat, direcció o horitzó no validats;
- convertir absència de consens en permís per operar;
- utilitzar text de notícies no atribuïble com a única evidència.

## Màquina d'estats operativa

El runtime funciona com una màquina d'estats explícita:

```text
WAIT
  └─ observació de context ─→ OPPORTUNITY
       └─ consell/quorum ───→ ARMED
            └─ senyal SQ ───→ ENTERING
                 └─ fill ───→ MANAGING
                      ├─ TP / SL / max_time ─→ EXITING ─→ COOLDOWN ─→ WAIT
                      └─ error o dades velles ─→ SAFE_EXIT ─────────→ WAIT
```

- `WAIT`: observa mercat, calendari i salut de dades; no hi ha permís d'entrada.
- `OPPORTUNITY`: un detector determinista identifica un context preregistrat.
- `ARMED`: el consell ha arribat a consens i emet un permís amb caducitat.
- `ENTERING`: el senyal SQ/Python coincideix i el motor calcula mida i leverage.
- `MANAGING`: la posició ja té TP, SL i `max_time` des del primer fill.
- `EXITING`: tancament normal per objectiu, stop o temps.
- `SAFE_EXIT`: sortida defensiva per dades, broker o invariants trencats.
- `COOLDOWN`: impedeix reentrades impulsives després del tancament.

Cada transició registra timestamp, dades utilitzades, causa i hash del contracte.
Reiniciar el procés recupera l'estat persistent; no pot duplicar una entrada.

## Gestor ràpid durant la posició

Durant `MANAGING` no s'espera el consell agentiu. Un gestor local determinista,
alimentat per preus frescos, pot moure l'SL segons una variant validada: break-even,
trailing ATR, trailing per estructura o bloqueig parcial de benefici.

Invariants obligatoris:

- l'SL protector existeix al broker des de l'entrada quan l'API ho permet;
- per a un long, el nou SL només pot ser igual o superior a l'anterior;
- per a un short, només pot ser igual o inferior;
- mai amplia la pèrdua màxima inicial ni supera el `max_time`;
- dades tardanes, preu invàlid o error de sincronització no mouen l'SL i poden
  activar `SAFE_EXIT`;
- les regles i freqüència de trailing formen part del backtest i de la paritat;
- un agent lent pot recomanar reduir risc o sortir, però mai anul·lar el TP/SL
  protector ni retardar una sortida obligatòria.

El gestor es provarà incloent gaps, ticks fora d'ordre, reconnexions, fills
parcials, modificacions d'ordre rebutjades i reinicis.

## Consens

Cada revisió produeix almenys quatre opinions independents i estructurades:

1. **Règim quantitatiu:** tendència, volatilitat, correlacions i liquiditat.
2. **Macro/calendari:** bancs centrals, inflació, ocupació i esdeveniments
   programats, prioritzant fonts oficials.
3. **Risc d'execució:** spread, slippage, rollover, mercat obert i salut de dades.
4. **Advocat del diable:** busca motius pels quals el context o les fonts poden
   ser erronis, tardans o ja incorporats al preu.

La decisió no es pren per prosa lliure. Cada opinió retorna:

```json
{
  "regime": "TREND|RANGE|SHOCK|UNCERTAIN",
  "confidence": 0.0,
  "allowed_actions": ["ENABLED_REDUCED"],
  "evidence": [{"source": "...", "observed_at": "..."}],
  "valid_until": "...",
  "vetoes": []
}
```

Un agregador determinista aplica quorum i vetos. Proposta inicial a validar:

- dades/executabilitat tenen veto absolut;
- notícia macro sense confirmació oficial no pot habilitar risc agressiu;
- `ENABLED_AGGRESSIVE` requereix acord de règim, macro i execució, sense veto;
- desacord material o evidència caducada resulta en `DISABLED` o
  `ENABLED_REDUCED`, mai en una decisió més agressiva.

## Exemple

L'estratègia SQ d'XAUUSD diu: “si hi ha compressió de 20 barres i el preu trenca
el canal, entrar a la barra següent amb stop ATR i caducitat de 12 hores”.

El consell observa una publicació d'IPC imminent, spread normal i volatilitat
prèvia baixa. No inventa l'entrada: pot habilitar la variant `SHOCK_BREAKOUT`
amb risc normal fins dues hores després de l'IPC. Si el spread s'amplia o la font
de dades queda endarrerida, el veto d'execució la desactiva.

## Validació necessària

Abans de paper, el consell s'executa en mode replay sobre context històric amb
fonts datades tal com eren conegudes llavors, evitant informació futura. Es
compara contra la mateixa cartera sense consell. Només passa si millora una
mètrica preregistrada de risc/retorn fora de mostra i no depèn d'una reescriptura
posterior de les explicacions.

En paper es registren inputs, opinions, consens, contracte final, senyal
determinista, sizing i execució. Live continua requerint autorització humana.
