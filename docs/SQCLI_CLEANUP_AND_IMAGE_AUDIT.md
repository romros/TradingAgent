# SQCLI: neteja segura i prova d'imatge mínima

Data de diagnosi: 2026-08-01. No s'ha modificat la imatge de producció.

## Evidència d'espai inicial

- Arrel SQ: 7.794.847.744 bytes assignats (~7,3 GiB).
- `internal/tmp/stock`: 804 JAR, 3.397.865.472 bytes assignats.
- `internal/testfiles`: 6 fitxers, 3.237.918.381 bytes lògics; tots creats avui.
- Logs amb més de 7 dies: cap.
- Contenidors one-off aturats: cap.
- `sqcli-docker` és el contenidor GUI persistent; no és candidat a eliminació.

`lab/sq_bridge/sqcli_cleanup.py` és dry-run per defecte. Amb `--apply` es nega a
actuar si qualsevol nom, imatge o comanda de contenidor actiu conté `sqcli`.
Només pot eliminar:

- `*.jar` sota l'arrel exacta `internal/tmp/stock`;
- logs `.log` de més de 14 dies;
- testfiles de més de 7 dies;
- contenidors aturats amb prefix exacte `sqcli-sqcli-run-`.

No executa cap prune global i no entra a `user`, History, projectes, configs,
llicències, resultats ni databanks. Cada execució JSON registra paths, bytes
assignats abans/després i contenidors eliminats.

## Auditoria del Dockerfile

- La capa `apt install` ocupa 354 MB.
- L'OpenJDK del sistema ocupa 194 MB.
- SQ inclou `j64` (342 MB) i els mapes del procés real confirmen llibreries
  carregades des de `/home/squser/SQ/j64`, no des de `/usr/lib/jvm`.
- `sqlite3` sí és necessari: `entrypoint.sh` l'usa per crear/actualitzar
  `internal/license.db`.
- `cron` està explícitament desactivat a `entrypoint.sh`; és candidat clar per a
  una imatge de prova, no per modificar directament producció.
- `fontconfig` pot ser necessari per GUI, gràfics o exportacions. Es conserva a
  la primera variant mínima.
- `j64/lib/src.zip` ocupa 52 MB. No és necessari en runtime Java normal, però es
  retirarà només en una segona variant després de provar compilació de snippets.

## Prova controlada futura

1. Construir una tag nova, mai substituir `sqcli-sqcli:latest`.
2. Primera variant: retirar només `openjdk-21-jre-headless` i `cron`; conservar
   `sqlite3`, `fontconfig` i tot `j64`.
3. Smoke real one-off: llicència, càrrega de dades, projecte discovery petit,
   retest, sync/export databank, `orders.csv` i arrencada GUI.
4. Comparar hashes/ordres amb la imatge actual i verificar zero errors/OOM.
5. Segona variant opcional sense `j64/lib/src.zip`; repetir el smoke incloent
   generació/compilació de snippets.
6. Promoure una variant només amb paritat funcional completa i rollback per tag.

Estalvi esperable que cal mesurar, no assumir: aproximadament 200–350 MB en la
primera variant; 52 MB addicionals si la segona variant supera el smoke.
