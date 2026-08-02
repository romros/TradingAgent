# Auditoria d'automatització web per StrategyQuant

## Decisió

`PINCHTAB_CONDITIONAL_PILOT / PLAYWRIGHT_FALLBACK / NO_INSTALL`

No s'ha instal·lat ni iniciat cap eina. Primer es demostra una operació necessària
que SQCLI no cobreix. L'automatització només actua sobre recerca SQ local; mai
sobre Ostium, BrokerageService o trading live.

## Ordre dels canals

1. Analitzar artifact existent, sense mutació.
2. Usar SQCLI si cobreix l'operació i exporta un resultat verificable.
3. PinchTab efímer per a un control exclusiu de la UI.
4. Playwright si el cas necessita una prova programada estable amb assertions i trace.
5. Checklist manual si l'estat no és observable o hi ha diàlegs natius.

## Comparació

| Criteri | PinchTab | Playwright |
|---|---|---|
| Orientació | agent + HTTP/CLI | framework de tests |
| Observació | text/snapshot accessible compacte | DOM, locators, assertions, trace |
| Dependències | binari Go + Chrome | Node + paquet + browsers |
| Estat normal | servidor, perfil potencialment persistent | context aïllat per test |
| Adequació SQ | exploració agentica d'un gap de UI | regressió d'un flux ja conegut |
| Risc | control complet del navegador i daemon per defecte | scripts/locators que envelleixen |

PinchTab guanya el primer pilot perquè el seu contracte petit és fàcil de conduir
des d'un agent i redueix snapshots. No s'accepten els defaults de daemon o perfil
reutilitzat.

## Contracte del pilot PinchTab

- versió fixada i checksum del binari abans d'executar;
- `pinchtab server`, mai `daemon install`;
- bind `127.0.0.1`, token aleatori fora de logs i cap port remot;
- config, state i perfil en directori temporal destruïble;
- allowlist només per l'origen local exacte de SQ;
- una instància i una pestanya; sense attach remot, proxy, JS eval o stealth;
- llegir snapshot i valor actual abans de cada mutació;
- després de click/fill, verificar text/valor postcondició;
- exportar configuració/resultat i calcular hash;
- aturar navegador i servidor sempre, inclòs error;
- no versionar cookies, traces sensibles ni screenshots de tercers.

## Gate d'adopció

Tres execucions consecutives sobre un projecte descartable han de produir el
mateix artifact i totes les postcondicions correctes. Un sol click ambigu, domini
inesperat, valor no llegible o procés residual torna el flux a manual. El pilot
no justifica un servei permanent.

Fonts: `pinchtab_official_2026`, `playwright_official_2026`.

## Pilot local executat

El gap d'exportació de codi queda demostrat: l'ajuda real de SQCLI 143.2708 només
ofereix `databank export` a CSV/XLSX i no exportació de codi d'estratègia.

Es va executar `pinchtab/pinchtab:0.11.0` fixada al digest
`sha256:295c842fbfa49e8de0634b896c0abd826562a838281b0902cf2df3c1ae2641ea`
com a contenidor `--rm`, sense port publicat, amb token efímer i xarxa compartida
només amb SQ. El health check fou correcte i Chrome va obtenir un snapshot de
`127.0.0.1:5050`, però SQ va respondre `Unable to resolve the request`: el procés
actual serveix `/call`, no la GUI. No es va invocar `-gui` perquè la descoberta
està activa.

El pilot també falla el gate de provenance: la imatge etiquetada `0.11.0` retorna
`pinchtab dev` com a versió del binari. El contenidor es va aturar i `--rm` el va
eliminar; la verificació posterior no trobà cap procés PinchTab residual.

Decisió actual: `PINCHTAB_TECHNICALLY_WORKS / PILOT_REJECTED / RETRY_AFTER_SQ`.
