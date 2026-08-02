# Prova local SQCLI — Build 143.2708

Data: 2026-08-02. Abast: inspecció de només lectura de la instància local i dels
artifacts d'Alquímia. No s'ha aturat ni modificat la campanya activa.

## Què queda demostrat

- `project list/status`, `databank list/count` i la lectura dels artifacts funcionen
  al build local. En la captura, el projecte `ALQUIMIA_XAU_H4_DISCOVERY` estava actiu,
  havia generat 71.375 candidats, n'havia acceptat 35 i no reportava errors.
- El símbol conté dades M1 de 2003-05-04 a 2026-03-13 i el candidat usa H4.
- L'instrument real llegit és `XAUUSD_C250_L20OST`: tick 0,001, spread 900,
  slippage per defecte 400 i pas de mida 0,001.
- `Strategy 0.7893.sqx` és llegible com a contenidor SQX i permet extreure build,
  motor, lògica, període, fingerprint i hipòtesis d'execució sense copiar el fitxer.
- El candidat només conté IS 2004-01-01/2015-02-06; OOS és buit. Per tant no és un
  finalista encara que el resultat IS sigui positiu.

## Insight de batalla

El número de fitness no és la realitat. En aquest cas, el fitxer mateix revela dues
portes obligatòries: falta tota validació posterior i el resultat usa slippage 300
mentre l'instrument declara 400. Alquímia ha de llegir i confrontar aquestes dades
abans de permetre que un candidat avanci.

## Capacitats CLI observades

L'ajuda local exposa operacions de projectes (incloent `startOnlyTask` i
`startFromTask`), databanks, símbols, instruments, importació/exportació de dades,
exportació MT4/MT5, ordres a CSV/XLSX i fitxers de comandes. Això cobreix la ruta
agentica principal sense navegador.

## Gap i decisió de navegador

Encara no hi ha un gap demostrat que justifiqui PinchTab o Playwright: SQCLI pot
carregar/desar configuracions i executar tasques. El navegador només s'activarà de
forma efímera si una configuració necessària no es pot expressar, inspeccionar o
validar per config/artifact/CLI. No s'ha instal·lat cap servei.

## Reproducció

```bash
python3 academia/tools/import_sqx_evidence.py \
  '/mnt/volume-SQ/user/projects/ALQUIMIA_XAU_H4_DISCOVERY/databanks/Results/Strategy 0.7893.sqx'
python3 -m unittest discover -s academia/tests -p 'test_*.py'
```

La primera ordre és només lectura i emet JSON a stdout; la segona valida el paquet.

## Inventari executat versus configurat

`audit_sq_artifacts.py` ha inspeccionat 1.574 SQX i els projectes locals. Hi ha 19
tasques Build, 57 Retest, una Optimize i una AutomaticPortfolioBuilder configurades.
Els artifacts contenen 486 resultats de precisió superior i 592 membres walk-forward,
però cap membre Monte Carlo ni additional-market. Per tant Monte Carlo continua sent
un gap real: veure l'opció al XML no prova que s'hagi executat.

El build objectiu 143.2708 tampoc conté cap tasca local d'Automatic Retest i la font
oficial catalogada situa aquesta funció al Build 144. El test de compatibilitat és
negatiu: l'expert ha de dir «no disponible en aquest build», no inventar un workflow.

La graella local d'extensions existeix sota `user/extend` per JForex, MT4, MT5,
EasyLanguage i pseudocodi; només hi ha dos fitxers CustomFunctions i cap plugin local.
No hi ha cap gap que justifiqui instal·lar una extensió o un navegador ara mateix.

```bash
python3 academia/tools/audit_sq_artifacts.py /mnt/volume-SQ/user/projects
```

## Runtime descartable per a les proves finals

El contenidor habitual no compleix l'abast d'escriptura: munta `user`, `internal` i
`logs` externs en mode RW. El dry-run de `prepare_sq_cow_runtime.py` ha calculat una
còpia writable de 5.430.649.740 bytes dins `academia/runtime/`, deixant els 16 GB
d'History en mount de només lectura. Hi ha 12.105.007.104 bytes lliures, suficients
amb el marge del 20%.

La còpia de 5,4 GB no s'executa mentre la descoberta està activa per no introduir
I/O competidora. En acabar, el runtime complet s'ha de preparar, provar amb `-h` i
eliminar després dels tres experiments. `academia/runtime/` està ignorat per Git.
