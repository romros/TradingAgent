# Tram 1 — Dades, hipòtesi i Builder

## Resultat d'aprenentatge

Preparar una campanya que pugui fallar honestament. Al final, una altra persona
ha de poder reconstruir què es va permetre cercar i quants intents es van fer.

## 1. Dades abans de regles

Congelar proveïdor, símbol, timezone, sessions, rang, timeframe, precisió i hash.
Registrar gaps i política de reparació. Configurar spread, slippage, comissió i
swap coherents amb el venue; no heretar silenciosament defaults de Data Manager.

Gate: no començar si dades i instrument no tenen versió o si l'IS/OOS no està
separat. Les dades més recents reservades no entren en generació ni selecció.

## 2. Convertir la idea en hipòtesi

Omplir abans de SQ:

```text
MECANISME: quin comportament explotem i per què podria persistir?
CONTEXT: en quins règims hauria d'aparèixer?
FALSADOR: quin resultat ens faria abandonar-lo?
ARQUITECTURA: simple, multi-TF/símbol, template o improvement?
COMPLEXITAT MÀXIMA: condicions, blocs, períodes, shifts i exits.
PRESSUPOST: candidats generats/avaluats, reinicis i famílies.
```

Un nom com «trend following» no és mecanisme. Una forma falsable seria: «després
d'una expansió direccional amb ADX alt, la persistència supera el cost durant N
bars; falla si l'expectativa neta és no positiva en dos trams de tendència no
usats per seleccionar».

## 3. Configurar What to build

- `Simple`: una sèrie i timeframe; primera opció si no hi ha necessitat causal
  d'un context addicional.
- `Multi-TF/symbol`: només si la hipòtesi menciona explícitament l'altra sèrie.
- `Template`: arquitectura pròpia amb punts aleatoris controlats.
- `Improve`: canvia parts declarades d'una estratègia existent; compta com nova
  cerca, no com una correcció innocent.

Decidir long/short i simetria a partir del mecanisme. Limitar condicions, shift i
períodes. Obligar una sortida: SL/PT o una regla alternativa. Evitar rangs físics
fixos quan preu o volatilitat varien materialment.

## 4. Seleccionar blocs

Cada bloc amplia l'espai de cerca. Permetre només famílies relacionades amb la
hipòtesi. Pesos, percentatges, parameter sets i rangs també són graus de llibertat
i entren al manifest. Calibrar magnituds dependents del mercat; no confondre
autocalibració amb validació d'una estratègia.

Una allowlist només diu què **pot** aparèixer. No obliga SQ a usar el mecanisme.
Si la hipòtesi exigeix, per exemple, entrada stop sobre canal, cal imposar-ne
l'arquitectura amb template/accions i comprovar després els artifacts. En el cas
local R1, 0/40 acceptades contenien `Highest`/`Lowest`; a R2, una arquitectura
`EnterAtStop` va donar cobertura 40/40. El segon resultat valida el contracte de
cerca, no l'edge.

## 5. Random o genetic

`Random` és una línia base transparent. `Genetic` afegeix selecció iterativa,
mutació, crossover, illes, migració, decimation, reinicis i fresh blood. Tots
augmenten els intents efectius. Comparar mètodes amb el mateix pressupost total,
no amb la mateixa durada aparent.

El filtre inicial ha de ser barat i poc selectiu: validesa, execució i mínim de
trades. Un PF alt al principi crea pressió de selecció prematura.

Els presets d'un tutorial són un punt de partida, no una recepta. Població 100,
100 generacions, crossover 90%, mutació 30%, quatre illes o Databank 2.000 poden
ser operables en un entorn concret, però tots canvien intents i selecció. Traduir
cada número a la seva funció, congelar-lo al manifest i mesurar el comptador real
abans de copiar-lo. Font exploratòria: `yt_easytrading_asapjylydw`, 05:11–09:52.

## 6. Databank i embut

El Databank conserva els millors segons ranking i té capacitat limitada; no és
el registre complet d'intents. Guardar `.sqx`, configuració, comptadors i motius
de descart fora de la memòria efímera del ranking. No deixar que una única
mètrica decideixi: usar mínim de trades, expectativa/costos, DD i concentració.

Separar sempre tres registres:

1. **intenció**: manifest i pressupost preregistrats;
2. **configuració**: què contenia realment el projecte;
3. **execució**: comptadors i estructura dels `.sqx` resultants.

No declarar que un pressupost governa la passada sense un stop/controller que ho
demostri. En una campanya local, el manifest deia 20.000 intents però el Builder
va parar amb 63 en omplir un Databank de 40.

## 7. Improver sense autoengany

Improver conserva una estratègia base i genera canvis només a les parts declarades:
entrada long/short, sortida, tipus d'ordre o condicions addicionals. És útil per
respondre una pregunta estreta, però no és una reparació gratuïta del candidat.

Contracte mínim:

1. congelar hash i mètriques de l'estratègia base;
2. declarar una sola part o família de parts modificable;
3. fixar blocs, complexitat, dades, ranking i pressupost de variants;
4. conservar la base com a control i comptar totes les variants provades;
5. comparar en dades no usades per triar la millora;
6. repetir precisió, costos i robustesa sobre la variant resultant;
7. mantenir-la només si millora el criteri preregistrat sense degradar els altres gates.

Si es modifiquen simultàniament entrada, sortida, ordre i sizing, no podem atribuir
la millora ni estimar-ne el cost de selecció. Si cap variant supera la base sota el
contracte congelat, la decisió correcta és conservar la base o descartar-la.

## Checklist de sortida

- [ ] dades i instrument versionats;
- [ ] holdout reservat i no consultat;
- [ ] mecanisme i falsador escrits;
- [ ] arquitectura i complexitat justificades;
- [ ] blocs i paràmetres limitats;
- [ ] artifacts contenen el mecanisme obligatori;
- [ ] pressupost d'intents inclou decimation i reinicis;
- [ ] el comptador executat, no només el manifest, queda registrat;
- [ ] ranking no substitueix l'inventari complet;
- [ ] costos preliminars inclosos;
- [ ] una sola raó preregistrada per avançar a Retester.
- [ ] si s'usa Improver, base, parts modificables i pressupost de variants congelats.

## Errors que l'expert ha de detectar

1. Habilitar tots els indicadors «per donar llibertat a SQ».
2. Afegir multi-timeframe sense mecanisme.
3. Canviar blocs després de veure OOS i conservar el mateix holdout.
4. Tractar 100 entrades del Databank com si només s'haguessin provat 100 models.
5. Comparar genetic i random ignorant decimation, poblacions i reinicis.
6. Usar stops en pips/dòlars no comparables entre règims o instruments.
7. Confondre una allowlist de blocs amb una arquitectura obligatòria.
8. Donar per executat un pressupost perquè apareix al manifest.
9. Dir «he millorat l'estratègia» comparant només la millor variant sobre les
   mateixes dades que l'han seleccionada.

Fonts: `sq_official_data_settings_20190109`,
`sq_official_what_to_build_20190109`, `sq_official_building_blocks_20190226`,
`sq_official_genetic_options_20190226`, `sq_official_databanks_20190121`.
Modes i Improver: `sq_official_build_modes_20190122` i
`sq_official_workflow_20190130`.
Cas local: `sq_local_sqx143_contract_drift_20260802`.
