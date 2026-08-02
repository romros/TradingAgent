# Tram 4 — Custom Projects, monitoratge i extensions

## Custom Projects

Automatitzar només després d'haver executat manualment i validat cada etapa.
Cada tasca té databank d'entrada/sortida, configuració versionada, gate i límit.

Flux de referència:

```text
clear temp → build finit → filtre barat → precisió → costos → MC → règims
→ finalistes → exportar artifacts → STOP
```

Els loops tenen límit d'iteracions, temps, intents i recursos. «Repetir fins a
tenir 100 estratègies» és selecció oberta si no hi ha pressupost global. Errors,
zero acceptance o databank buit aturen; no relaxen filtres automàticament.

## Automatic Retest

Serveix per tornar a mesurar estratègies congelades amb dades noves. No modifica
regles ni llindars. Registrar hash d'estratègia, dades anteriors/noves, engine i
overrides. Les opcions Strategy/Custom/Instrument poden produir costos diferents;
cal declarar-ne una.

Estats:

- `HEALTHY`: dins bandes preregistrades;
- `WATCH`: degradació amb mostra encara insuficient;
- `PAUSE`: supera DD/cost/error o paritat falla;
- `RETIRE`: evidència nova suficient contra el mecanisme;
- `DATA_ERROR`: dades/configuració no comparables.

Mai reoptimitzar automàticament després de `PAUSE`; això inicia una nova campanya.

## Custom analysis i snippets

Afegir extensió només si SQ no pot calcular una dada que canvia la decisió.
Contracte mínim: problema, build, codi font, test, dependències, traducció al
target, resultat abans/després i reversibilitat. Una mètrica custom que filtra
augmenta l'espai de selecció i s'ha de preregistrar.

Custom analysis per estratègia corre després de backtests/cross-checks i abans de
guardar; per databank pot comparar o eliminar múltiples resultats dins Custom
Projects. No cridar scripts externs sense timeouts, esquema i validació de retorn.

## Grid

Grid reparteix còmput; no millora evidència per si sol. Fixar el pressupost abans
d'escalar, registrar nodes/builds/dades i comprovar determinisme en una mostra.
No usar grid si el coll d'ampolla és zero acceptance, hipòtesi feble o filtres
incorrectes.

Fonts: `sq_official_custom_projects_20200504`,
`sq_official_automatic_retest_144`, `sq_official_extensibility_20210804` i
`sq_official_program_layout_20190226`.
