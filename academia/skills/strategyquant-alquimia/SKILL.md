---
name: strategyquant-alquimia
description: Design, review, and explain StrategyQuant research campaigns for Alquímia using evidence-based, practical decisions. Use when an agent must plan Builder/Retester/Optimizer workflows, assess generated strategies, choose robustness tests, diagnose overfitting or contaminated holdouts, compare candidates, or turn StrategyQuant results into a concise continue/test/reject recommendation. Do not use it to execute live trades or promise profitability.
---

# StrategyQuant Alquímia

Actuar com a investigador pràctic. Cercar estratègies que mereixin una prova nova,
no backtests que simplement semblin espectaculars.

## Flux principal

1. Definir mercat, timeframe, capital, costos, drawdown i freqüència.
2. Congelar dades, pressupost d'intents, filtres i holdout abans de generar.
3. Construir barat; aplicar proves cares només als supervivents.
4. Provar que intenció, configuració i artifacts executats coincideixen.
5. Revisar estabilitat, concentració, costos, intents i contaminació.
6. Validar mecanisme, règims comparables i economia executable avui.
7. Donar `CONTINUAR`, `PROVA DIRIGIDA` o `DESCARTAR`.
8. Proposar una sola prova següent; no obrir una cerca per salvar un candidat.

## Carregar només el necessari

- Per dissenyar una campanya, llegir [campaign.md](references/campaign.md).
- Per configurar dades, hipòtesi i Builder, llegir [builder.md](references/builder.md).
- Per escollir o interpretar proves, llegir [robustness.md](references/robustness.md).
- Per revisar candidats, llegir [decision.md](references/decision.md).
- Per autoritat, evidència i límits, llegir [evidence.md](references/evidence.md).
- Per aprendre d'artifacts i fracassos, llegir [learning.md](references/learning.md).
- Per passar del backtest a la realitat, llegir [regimes.md](references/regimes.md).
- Per cartera, exportació, automatització i monitoratge, llegir [operations.md](references/operations.md).

## Regles de batalla

- Comptar intents; si no es coneixen, declarar confiança baixa.
- Tractar una execució sense errors només com a gate operatiu, no com a evidència.
- No confondre blocs permesos amb un mecanisme obligatori; inspeccionar artifacts.
- Tractar qualsevol holdout consultat com a dades de desenvolupament.
- Incloure spread, comissió i slippage abans de comparar.
- Preferir regions estables a pics aïllats.
- Penalitzar pocs trades, benefici concentrat, drawdown i complexitat.
- No confondre `pass` amb rendibilitat futura.
- No canviar criteris després de veure resultats sense nova campanya.
- No promoure cap finalista sense informe de règims i economia actual.
- No tocar BrokerageService, Ostium ni execució de trading.

## Format de resposta

```text
DECISIÓ: CONTINUAR | PROVA DIRIGIDA | DESCARTAR
MOTIU: màxim dues frases
RISC PRINCIPAL: un
SEGÜENT PAS: una sola acció concreta
EVIDÈNCIA: font, locator o experiment; indicar si falta
```

Separar fets observats, inferències i recomanacions. Afegir només detalls que
canvien la decisió.

## Revisió determinista

Quan l'entrada tingui els camps de `references/decision.md`, executar:

```bash
python3 scripts/review_candidate.py candidate.json
```

Usar la sortida com a control mínim, no com a senyal de trading.

Quan hi hagi gates temporal i de costos d'Alquímia, normalitzar-los amb
`academia/tools/import_alquimia.py` abans de raonar. Consultar
`academia/experiments/failure-memory.json` per evitar repetir una direcció rebutjada.
Per explicar una família ja registrada amb format estable, executar
`academia/tools/campaign_advisor.py FAMILY`; si no té evidència, no extrapolar
una altra família.

Abans d'interpretar una passada SQ, comprovar el contracte executat amb
`academia/tools/verify_sq_contract.py`: declarar els tokens estructurals,
crosschecks exactes i valors de configuració que importen. Un `pass` d'aquesta
eina només permet començar la interpretació; no valida robustesa ni benefici.

Després de qualsevol Improver, executar també:

```bash
python3 academia/tools/lint_sqx_semantics.py VARIANT.sqx --base BASE.sqx
```

Per una prova restringida a stop-loss/profit-target:

```bash
python3 academia/tools/lint_sqx_semantics.py VARIANT.sqx --base BASE.sqx --allow-slpt-change
```

Aquest mode només aprova si SL/PT canvia realment i entrada, ordres sense els
paràmetres SL/PT i senyals de sortida queden preservats. Sense variant desada no
es pot declarar provat l'aïllament, encara que el log mostri variants generades.

Rebutjar si detecta un senyal constant o deriva d'entrada/ordres congelades. Un
`pass` només confirma aquest contracte semàntic mínim; encara cal validació fora
de mostra, costos, règims i economia real.

Per una prova entry-only, afegir `--allow-entry-change`: això permet diferències
als senyals d'entrada però continua exigint que les ordres quedin congelades. Si
no hi ha supervivents, registrar els motius i no relaxar filtres post hoc.
