# Mapa complet de StrategyQuant per a Alquímia

L'objectiu no és dominar botons. És convertir una idea de mercat en una decisió
auditable sobre si mereix una prova real. Aquest és l'ordre operatiu; saltar una
etapa invalida les següents.

| Ordre | Capacitat SQ | Per a què serveix | Sortida exigida abans d'avançar |
|---:|---|---|---|
| 0 | Global config / versió | Congelar entorn i recursos | build, plataforma, llavor i pressupost |
| 1 | Data Manager / instruments | Dades, sessions, spread, swap, comissió | manifest de dades i especificació del venue |
| 2 | Hipòtesi + AlgoWizard/templates | Expressar el mecanisme i limitar l'espai de cerca | hipòtesi falsable, arquitectura i blocs permesos |
| 3 | Builder / Improver | Generar candidats dins l'espai preregistrat | databank brut i nombre d'intents |
| 4 | Ranking / filters / databanks | Fer el primer embut barat | supervivents, descartats i motiu |
| 5 | Retester / cross-checks | Canviar precisió, dades, mercats i costos | sensibilitat, no un segon ajust |
| 6 | Monte Carlo / parameter tests | Mesurar fragilitat d'ordres, dades i paràmetres | distribucions i límits de pèrdua |
| 7 | Optimizer / WFO / WFM | Comprovar estabilitat local i reoptimització | regió estable; mai el millor punt sol |
| 8 | Regime + reality transfer | Passar dels números al mecanisme actual | règims, costos, mida, marge i liquidació actuals |
| 9 | Portfolio / Portfolio Composer | Mesurar contribució marginal i dependències | correlació, risc conjunt i concentració |
| 10 | Export / cross-platform check | Verificar equivalència del motor objectiu | codi, dades i resultats conciliats |
| 11 | Custom Projects | Automatitzar només el flux ja validat | pipeline reproduïble amb gates tancats |
| 12 | Automatic Retest / monitoratge | Detectar degradació amb dades noves | criteris previs de pausa o retirada |
| 13 | Code Editor / snippets / grid | Estendre blocs o escalar còmput quan cal | prova de necessitat, test i control de versió |

## Tres camins, no un

- Si coneixem la lògica: `Dades → AlgoWizard → Retester → robustesa → realitat`.
- Si descobrim lògica: `Dades → hipòtesi limitada → Builder → embut → robustesa → realitat`.
- Si ja tenim estratègies: `Importar .sqx → Retester → realitat → cartera`.

Custom Projects va al final de l'aprenentatge: automatitzar un procés mal pensat
només produeix errors més ràpid. Optimizer no rescata una estratègia sense edge;
Portfolio no rescata components amb expectativa negativa; grid no substitueix un
pressupost d'intents.

## Cobertura pendent explícita

Aquest mapa cobreix la funció dels mòduls. Encara cal verificar, sobre el build
objectiu, cada control, rang, format d'import/export i diferència del motor. Cada
element nou passa de `captured` a `tested` només amb una prova local reproduïble.

Fonts: `sq_official_program_layout_20190226#section:main`,
`sq_official_workflow_20190130#section:blueprint` i manifests oficials específics
de l'Acadèmia.
