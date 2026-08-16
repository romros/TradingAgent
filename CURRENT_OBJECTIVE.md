# Objectiu canònic actual — cartera teòrica nova amb SQCLI

**Vigent des de:** 2026-08-12
**Esmena de criteri d'èxit:** 2026-08-16
**Autoritat:** aquest document preval sobre qualsevol full de ruta anterior.

## Criteri d'èxit vigent — superar la inversió passiva

L'objectiu final de TradingAgent no és només trobar estratègies amb PnL
positiu. Ha de produir una cartera que, amb la mateixa finestra, capital,
unitats, dades i costos:

1. superi buy-and-hold net de costos en rendiment; **o**
2. si el rendiment és inferior, ofereixi una millora prou clara de risc-retorn
   (drawdown, Sharpe/Sortino i retorn sobre drawdown) per justificar la
   complexitat operativa.

La cartera actual de cinc edges queda congelada com a **baseline defensiva**,
no com a objectiu assolit. El seu resultat 2022–2024 és +19,32% acumulat
(~6,07% CAGR) i DD diari conjunt 10,92% sobre 3.000 USD. És prometedora per
control de risc, però encara no ha demostrat que sigui millor que una inversió
passiva adequada.

No es pot convertir una estratègia mediocre en guanyadora aplicant leverage.
Primer s'exigeix edge net i comparació de benchmark; compounding i
palanquejament només s'avaluen després. Els benchmarks s'han de preregistrar
abans de calcular-los i no es poden canviar retrospectivament per facilitar un
PASS.

El capital no està prefixat. S'han d'avaluar configuracions fins a un màxim de
**3.000 USD** i recomanar el capital més petit que superi el contracte de
benchmark amb operativa realista. Si cap nivell ho fa, la decisió correcta és
no assignar encara capital al trading actiu.

La cartera final tindrà **entre 6 i 8 estratègies i mai més de 8**. El mínim de
sis no autoritza a admetre peces mediocres: mentre no existeixin sis edges que
passin individualment els gates, la biblioteca continua incompleta. Cada
estratègia ha de mantenir identificador, regla congelada, senyals, capital,
fills, costos, PnL, drawdown i estat de salut separats. L'agregació de cartera
no pot ocultar la degradació d'una peça; s'han de poder desactivar i auditar
individualment.

Estat canònic de la baseline:
[`docs/FIVE_STRATEGY_PORTFOLIO_STATUS.md`](docs/FIVE_STRATEGY_PORTFOLIO_STATUS.md).

## Objectiu anterior — TANCAT

La cartera Ostium/Alquímia queda conservada únicament com a evidència històrica
i metodològica. No se'n reutilitzen candidats ni holdouts en aquesta recerca.
No s'han de reprendre els workers, probes ni desplegaments d'aquell objectiu.

## Decisió vigent

Construir i falsar amb **StrategyQuant/SQCLI** una cartera teòrica nova de
trading sistemàtic, formada només per mercats tradicionals que constin al
catàleg públic d'IBKR. La recerca comença de zero: no s'hi poden reciclar
actius, candidats, holdouts ni conclusions de les campanyes Ostium/Alquímia.
StrategyQuant/SQCLI és el motor principal de descoberta; Python serveix per
auditar i reproduir els resultats, no per saltar-se l'embut preregistrat.

Ara **no** es desenvolupa cap integració amb IB Gateway, TWS, BrokerageService
o un compte IBKR. Aquesta feina només s'autoritza si abans existeix una cartera
teòrica que superi tots els gates i sembli econòmicament útil.

La guia completa per reprendre el projecte és:

[`docs/NEW_IBKR_SQ_PORTFOLIO_SESSION_HANDOFF.md`](docs/NEW_IBKR_SQ_PORTFOLIO_SESSION_HANDOFF.md)

La selecció de famílies es basa en:
[`docs/EVIDENCE_BASED_STRATEGY_FAMILIES.md`](docs/EVIDENCE_BASED_STRATEGY_FAMILIES.md).

## Resultat buscat

- Entre 6 i 8 estratègies complementàries; mai completar la xifra amb
  estratègies mediocres.
- Cap criptoactiu.
- Actius nous respecte de l'univers Ostium anterior i verificables al catàleg
  públic d'IBKR.
- Regles d'entrada, sortida i risc deterministes.
- Retorn ambiciós i compounding, però sense convertir un sistema de valor
  esperat negatiu en atractiu mitjançant leverage.
- Modelar explícitament capitals de 200, 400, 500, 700, 1.000 i 2.000. Un
  50% anual pot ser un escenari aspiracional, mai una garantia ni un criteri per
  forçar el resultat.
- Operacions preferentment curtes i oportunistes, sempre que l'evidència ho
  sostingui; no cal operar cada dia.
- `NO_CANDIDATE` és un resultat correcte.

## Línies tancades — només evidència històrica

No són candidates de la cartera nova: US500/IBUS500/SPY, QQQ/NDX, NVDA,
EURUSD, XAU, TLT, els paper probes antics i qualsevol actiu o estratègia
investigats sota Ostium/Alquímia. Tampoc no es reprenen els workers antics.

Excepció explícita del 2026-08-12: AAPL, GOOGL, MSFT i TSLA s'autoritzen com a
cohort nova. En el cas de MSFT, només recerca neta amb `MSFTUSUSD` Dukascopy;
queden prohibits el recurs Yahoo, candidats, paràmetres i holdouts antics.

Els resultats US500/SPY continuen sent útils per aprendre metodologia, costos i
errors de mapping, però **no** compten com a cartera actual.

## Fases i checkpoints

- [x] Tancar la línia Ostium i el trasllat IBUS500/SPY.
- [x] Confirmar que SQCLI funciona i queda sense projectes actius.
- [x] Fer neteja segura dels JAR temporals regenerables i smoke test.
- [x] Crear el registre segregat i validable de 13 candidats; quatre mega-caps
  han estat reautoritzades explícitament sota un contracte clean-slate. La
  prova pública general de presència a IBKR;
  la verificació individual i els permisos continuen pendents.
- [ ] Localitzar dades certificables, preferentment Dukascopy o una font
  primària adequada; Yahoo no és font de certificació.
- [x] Executar el primer preflight CAT sense mirar rendiment: feed públic
  recent/Data Manager bloquejats, però ruta BI5 històrica reprenable 2017
  `PASS_YEAR_PILOT_SOURCE_ONLY` (163 sessions RTH íntegres).
- [ ] Estendre CAT 2018–2025 per anys acotats i certificar ajustos corporatius.
  Checkpoint: 2018 té gener–juliol complets; agost/setembre són reprenables des
  de cache i octubre–desembre no iniciats. No queda cap procés actiu.
- [ ] Preregistrar per campanya: hipòtesi, actiu, timeframe, direcció, sessions,
  costos genèrics, particions temporals, gates i regla d'aturada.
- [ ] Executar l'embut SQCLI començant per D1 i baixar de timeframe només quan
  una família mostri evidència estable.
- [ ] Fer validació temporal sense censura i robustesa: precisió superior,
  costos, Monte Carlo, pertorbació de paràmetres i walk-forward quan pertoqui.
- [ ] Reproduir els finalistes independentment en Python.
- [ ] Construir cartera i mesurar correlació, concurrència, drawdown, risc de
  ruïna i sensibilitat del compounding al capital.
- [ ] Decidir `THEORETICAL_PASS` o `NO_CANDIDATE`.
- [ ] Només amb `THEORETICAL_PASS`: verificar instruments, permisos, PRIIPs,
  mida mínima, marge, comissions i API del broker.
- [ ] Paper màxim 14 dies i live només amb nova autorització humana explícita.

## Regles inviolables

No obrir el holdout per ajustar; no relaxar gates després de veure resultats;
no barrejar evidència antiga amb la nova; no prometre rendibilitat; no iniciar
infraestructura IBKR abans del `THEORETICAL_PASS`.
