# Casos de perfils guanyadors d'Ostium

Data de tall: 2026-08-13. Estudi exploratori, només lectura. No autoritza copiar
trades, seguir wallets ni operar. L'objectiu és descobrir comportaments que
mereixin una hipòtesi pròpia i falsable per al compte de 200–500 USDC.

## Dades i límits

- Font: `OstiumSubgraphClient.getFillsByTime({user: "ALL"})` de
  `@ostium/builder-sdk@0.7.0`.
- 80.000 fills públics únics entre 2026-06-05 15:17 UTC i 2026-08-13 10:27 UTC.
- 41.336 fills de tancament amb collateral positiu; 1.811 wallets.
- `closedPnl` és PnL realitzat net d'opening fee, oracle i rollover segons el
  contracte de l'SDK.
- Els quatre exports crus viuen temporalment a `/tmp`, no es versionen. SHA-256:
  `28e50d...acb474`, `eefda7...47ac6`, `4a243b...52f8` i
  `823824...cb481`.
- La finestra és curta, coincideix amb un únic conjunt de règims i els trams
  arriben al límit de 20.000 files. No és una cohort completa de vida del compte.
- PnL per collateral de cada tancament no és retorn de compte: pot comptar
  collateral reutilitzat i posicions simultànies.

## Filtre contra falsos guanyadors

El filtre exploratori exigeix ≥50 tancaments, ≥20 dies actius, collateral mediana
≤1.000 USDC, percentil 90 ≤1.500 USDC, PnL total/mitjà/medià positius, cap
liquidació i retorn mitjà positiu en cadascun de tres trams cronològics.

| Etapa | Wallets |
|---|---:|
| Amb algun tancament | 1.811 |
| Mostra, durada i mida compatibles | 63 |
| PnL total, mitjà i medià positius | 11 |
| També 0 liquidacions i 3/3 trams positius | 6 |

El 0,33% final no estima la probabilitat de guanyar: hi ha selecció de
supervivents, múltiples comptes per persona i comptes començats abans del tall.

## Tres casos no-crypto informatius

Els identificadors són SHA-256 de la wallet en minúscules per evitar convertir
l'estudi en una llista de copy-trading.

### Cas A — swing de commodities

- id `8d1bdf...829fbf`; 55 tancaments, 32 dies, +2.801,77 USDC.
- Collateral mediana 242 USDC; p90 497; durada mediana 31 h.
- WTI 23 trades i +2.004 USDC; plata 18 i +727; coure 4 i +108.
- Or: 3 trades i −143 USDC. Mediana de leverage 15x; màxim 100x.
- 47 sortides manuals i 8 stops; cap liquidació observada.

Insight: la selecció entre commodities i la captura multi-dia semblen més
importants que operar «metalls» genèricament. El màxim 100x i el pes del WTI fan
que no sigui un model de risc transferible directament.

### Cas B — tendència lenta de commodities

- id `817259...774bb`; 101 tancaments, 28 dies, +594,58 USDC.
- Collateral mediana 21,69 USDC; p90 59,69; leverage 3–4x.
- Durada mediana 505 h (~21 dies); totes les posicions són long.
- WTI aporta +579,52; plata −63,71; coure +64,61; pal·ladi +14,16.
- 77 sortides manuals, 17 take-profits i 7 stops; cap liquidació.

Insight: és el cas més compatible amb un compte petit i risc moderat, però pot
ser només exposició al règim alcista de commodities. Cal falsar-lo en règims
laterals i baixistes i carregar rollover real abans d'imitar-ne el mecanisme.

### Cas C — multi-mercat temporal

- id `3001b7...3bc6e`; 301 tancaments, 30 dies, +217,75 USDC.
- Collateral gairebé fix: mediana 149,15 i p90 149,45 USDC.
- Leverage mediana 10x; durada mediana gairebé exacta de 6 h.
- Guanya en WTI (+98,61), XAU (+53,34) i coure (+35,29), però perd en US100,
  Brent, BTC i USD/JPY. Només té un trade US500.
- Les 301 sortides són manuals; cap liquidació.

Insight: sembla una regla horària automatitzada i diversificada, però l'avantatge
és petit (retorn mitjà 0,53% del collateral tancat) i heterogeni per actiu. És una
font d'hipòtesi sobre horitzons, no una estratègia copiable.

## US500 i decisió de focus

Cap wallet compleix el filtre robust i alhora té ≥20 tancaments US500. Els casos
amb activitat US500 mostren liquidacions, deteriorament entre trams, PnL negatiu o
mostra massa petita. Per tant, l'activitat pública no justifica perseguir
scalping, copiar traders ni declarar US500 com el millor mercat.

Si comencéssim de zero, el focus de recerca seria:

1. edges de baixa rotació amb horitzó multi-hora o multi-dia;
2. selecció de mercat/règim abans que una regla fixa per un sol actiu;
3. commodities com a font d'hipòtesis causals (trend/carry/escassetat), no com a
   permís per reobrir les famílies de preu XAU ja rebutjades;
4. leverage només després de demostrar expectativa neta, amb cap 5x per al nostre
   compte;
5. continuar el gate US500 ja preregistrat; si passa, provar una única família de
   baixa rotació. Si falla, no insistir en M15.

## Dinàmica social

No es construeix graf social ara. Els tres casos usen builder zero, les cerques
públiques no aporten identitat fiable i els fills no exposen relacions de referral.
El programa de punts premia activitat i referrals, de manera que popularitat,
volum i ranking estan confosos amb incentius. Un graf d'entrades simultànies també
confondria còpia amb reacció comuna a notícies.

Només justificaria el graf si una cohort sobreviu ≥6 mesos i existeixen arestes
observables independents (builder/referral compartit o retard repetible després
d'un líder). Fins llavors, el retorn marginal és inferior a estudiar règims,
durada, costs i risc.

## Decisió

`HYPOTHESIS_SOURCE_ONLY`. No hi ha candidat promocionable ni canvi d'univers.
L'aprenentatge útil és buscar mecanismes lents i condicionats per règim, i rebutjar
leaderboards, leverage i una ratxa curta com a proves d'edge.

