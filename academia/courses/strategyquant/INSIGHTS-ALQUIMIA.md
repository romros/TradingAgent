# Què sap fer ara l'expert StrategyQuant d'Alquímia

## La idea central

StrategyQuant pot fabricar molts backtests bons. L'expert d'Alquímia no intenta
augmentar aquest nombre: redueix candidats fins quedar-se amb els que aporten
evidència menys fràgil i indica la prova següent més barata que resol un dubte.

## Insights que aplica

1. **Generar no és validar.** Builder proposa candidats; Retester i els experiments
   comproven si sobreviuen fora de les condicions que els van seleccionar.
2. **El cost forma part de l'estratègia.** Spread, slippage, comissió i swap no són
   decoració final. Sense ells, no es compara ni promociona.
3. **Ràpid primer, precís després.** Generar amb una simulació barata i retestar
   només supervivents amb la precisió adequada evita gastar càlcul inútil.
4. **Funnel, no arbre de Nadal.** Posar tots els cross-checks al Builder és lent i
   poc informatiu. Cada fase barata elimina candidats abans de la següent.
5. **Una prova, una pregunta.** Monte Carlo trades pregunta per seqüència/omissions;
   retest Monte Carlo pregunta per dades/paràmetres/costos; WFM, per calendari.
6. **Regió abans que pic.** Un veïnat estable de paràmetres o WFM és preferible a
   una combinació espectacular aïllada.
7. **Comptar intents.** Milers de variants fan més probable trobar un guanyador per
   casualitat. El pressupost es fixa abans i no s'allarga per trobar un pass.
8. **Holdout d'un sol ús.** Si el resultat final guia un canvi, ja és desenvolupament.
9. **Benefici repartit.** Un sol run, any, símbol o trade no ha de sostenir el cas.
10. **Pocs trades = incertesa.** No és un rebuig automàtic, però exigeix més
    observacions sense canviar les regles.
11. **Custom Project necessita aturada.** “Omplir el Databank final” pot convertir-se
    en cerca indefinida; cal pressupost d'intents/temps.
12. **Continuar no és desplegar.** Només significa que el candidat mereix consumir
    la prova següent.

## Com dissenyaria una campanya petita

```text
1. Hipòtesi i costos congelats
2. Builder ràpid amb pressupost finit
3. Retest precís dels supervivents
4. Monte Carlo trades barat
5. Sensibilitat petita de paràmetres/costos
6. WFM 3×3 només si es reoptimitzarà
7. Revisió: descartar / prova dirigida / continuar
8. Holdout final una vegada
```

No hi ha percentatges màgics. Els llindars depenen de timeframe, freqüència,
capital i família d'estratègia, però s'han de declarar abans de veure candidats.

## Exemple de resposta de l'agent

```text
DECISIÓ: PROVA DIRIGIDA
MOTIU: la WFM té una regió estable, però només hi ha 82 trades i un run aporta 57%.
RISC PRINCIPAL: concentració del resultat.
SEGÜENT PAS: ampliar el període sense canviar regles i repetir només el resum per run.
EVIDÈNCIA: sq_official_walk_forward_values_20190101#section:concentration
```

## Què encara no sap

- quins llindars funcionen millor per a les famílies d'Alquímia;
- com es comporten aquests gates a la build instal·lada;
- quins artifacts reals exposen els camps necessaris;
- si algun insight queda contradit per campanyes reals.

Això s'aprendrà important artifacts en mode només lectura. Fins llavors, la skill
és assessora de recerca, no generadora autònoma ni sistema de trading.
