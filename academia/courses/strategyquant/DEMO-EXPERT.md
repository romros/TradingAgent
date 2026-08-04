# Demostració entenedora: què aporta l'expert

Tenim tres estratègies fictícies. No comparem qui guanya més al backtest; comparem
quina mereix consumir el següent tros de dades intactes.

## A — Pic espectacular

- 180 trades i costos inclosos;
- només passa 1 de 9 cel·les WFM;
- concentra el 68% del benefici en un run;
- s'havien pressupostat 1.000 intents, però se n'han fet 1.450;
- el holdout ja s'ha consultat dues vegades.

**Decisió: descartar.** El resultat pot semblar el millor, però s'ha continuat
buscant més enllà del pressupost i les dades reservades ja han guiat decisions.
Buscar una nova combinació només augmentaria l'autoengany.

## B — Prometedora però verda

- 82 trades quan el mínim declarat era 150;
- passa 6 de 9 cel·les i cinc formen una regió;
- el 57% del benefici depèn d'un sol run;
- costos inclosos i holdout intacte.

**Decisió: prova dirigida.** No es descarta perquè hi ha estabilitat regional, però
tampoc es consumeix encara el holdout final. Següent pas únic: obtenir més
observacions sense canviar les regles i comprovar si baixa la concentració.

## C — Consistent

- 236 trades i costos inclosos;
- passa 7 de 9 cel·les; sis formen una regió;
- el run principal aporta el 31% del benefici;
- 804 intents d'un pressupost de 1.000;
- holdout intacte i drawdown dins del límit.

**Decisió: continuar.** No significa “comprar” ni “anar a live”. Significa que és
la candidata que mereix una única prova final sobre dades intactes. Després no es
podran ajustar regles mirant aquell resultat.

## Aprenentatge real

Si només miréssim benefici, probablement escolliríem A. L'expert selecciona C
perquè la seva evidència és menys contaminada i menys concentrada. Aquest és el
valor de l'acadèmia: no inventa una estratègia guanyadora; evita gastar el holdout
i el temps de recerca en candidats que semblen bons per motius febles.

## Límits

Les tres estratègies són exemples sintètics. La demostració prova la lògica de
decisió, no StrategyQuant ni rendibilitat. Per aplicar-la a una campanya real cal
importar aquests onze camps dels seus artifacts, sempre en mode només lectura.

## Prova cega de transferència

La suite versionada afegeix cinc casos que el pont no pot confondre: dades
desconegudes, compte inviable, dependència d'un règim antic, autorització per
obrir holdout i autorització només per preparar paper trading.

```bash
python3 academia/tools/benchmark_reality_transfer.py \
  academia/experiments/examples/reality-transfer-battle-cases.json
```

Un 5/5 només prova coherència de la política. No prova que els inputs d'una
campanya real siguin certs; aquests continuen necessitant artifacts i fonts.
