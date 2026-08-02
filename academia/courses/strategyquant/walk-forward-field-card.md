# Fitxa de batalla — Walk-Forward Matrix

## Quan usar-la

Quan una estratègia ja té prou trades, costos realistes i un OOS de desenvolupament
acceptable, i vols saber si depèn massa d'un calendari concret de reoptimització.

## Prova inicial barata

Comença amb una graella petita de 3×3. No busquis precisió fina:

- tres nombres de runs separats;
- tres percentatges OOS raonables;
- pocs paràmetres importants, no tots;
- mateixos costos i dades que al backtest base.

Si aquesta prova falla clarament, no ampliïs la graella per intentar trobar una
casella guanyadora. Descarta o torna a la hipòtesi de l'estratègia.

## Què mirar

1. Hi ha un bloc de cel·les veïnes acceptable?
2. Els runs tenen prou trades?
3. El benefici està repartit entre runs?
4. El drawdown continua assumible?
5. La versió reoptimitzada aporta alguna cosa respecte de l'original?

## Semàfor

- **Verd per continuar investigant:** regió estable, costos inclosos, resultat
  repartit i cap dependència clara d'un sol run.
- **Ambre:** passa però amb pocs trades, concentració o diferències fortes entre
  cel·les. Cal una prova dirigida, no més cerca indiscriminada.
- **Vermell:** només funciona un pic, cal relaxar criteris després de veure el
  resultat, o el holdout ja ha guiat canvis. Atura i no promocionis.

## Registre mínim

Build SQ, dates, símbol/timeframe, costos, paràmetres, graella, nombre d'intents,
criteris de pass i hash/configuració. Res més si no ajuda a prendre una decisió.

## Sortida que ha de donar l'agent

```text
DECISIÓ: continuar / prova dirigida / descartar
MOTIU: dues frases
RISC PRINCIPAL: un
SEGÜENT PAS: una sola prova concreta
EVIDÈNCIA: source_id#locator o experiment_id
```
