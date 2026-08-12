# CHECK 4 — preregistre de la campanya no-cripto v5

**Estat:** `PASS_NONCRYPTO_CAMPAIGN_PREREGISTRATION`

**Segell:** `bb637db2c65d947218d8ba49a6b0ac0ae27fcf50950b01df52821708f0a54a20`

**Contracte:**
[`noncrypto_campaign_preregistration_v5.json`](../lab/sq_bridge/noncrypto_campaign_preregistration_v5.json)

No s'ha executat SQCLI, ni consultat performance o holdout. Paper i live romanen
bloquejats.

## Divisió temporal

| Mercat | Train | Validació | OOS | Holdout ocult |
|---|---|---|---|---|
| XAUUSD/JPY M15 | 2007–2018 | 2019–2022 | 2023–2024 | 2025–28/02/2026 |
| EURUSD D1 | 2003–2017 | 2018–2021 | 2022–2024 | 2025–31/07/2026 |
| US500 D1 | 2018–2021 | 2022–2023 | 2024 | 2025–08/07/2026 |

`Train` construeix. `Validació` filtra. `OOS` prova dades no utilitzades en la
construcció. El `holdout` només s'obre una vegada per a un màxim de 12 candidats,
després de superar tots els altres gates; un fail implica rebuig sense retuning.

## Pressupost SQ evolutiu

| Família | Avaluacions màximes |
|---|---:|
| XAU compressió-breakout | 16.000 |
| XAU xoc fallit-reversió | 16.000 |
| USDJPY rang-breakout | 16.000 |
| USDJPY breakout fallit | 10.240 |
| US500 rebot de xoc | 9.280 |
| EURUSD tendència curta | 9.280 |
| **Total** | **76.800** |

SQ usa quatre illes de 80 individus, migració cada 10 generacions i màxim 50
generacions segons el pressupost de cada família. Pot aturar després de la
generació 20 si el front de Pareto no millora almenys 0,5% durant vuit
generacions. Mai ampliarem pressupost després de veure performance.

`Pareto` aquí vol dir conservar solucions que representen compromisos diferents:
per exemple, una pot tenir més benefici però més drawdown, i una altra menys
benefici però més estabilitat. Una no domina l'altra en tots els criteris.

## Gramàtica i claredat

- Màxim tres condicions d'entrada i tres eixos sensibles.
- Profunditat màxima quatre; sense blocs de volum.
- Senyal al close, entrada al següent open i col·lisió intrabar `STOP_FIRST`.
- TP/SL/temps màxim en plantilles explícites.
- Context/notícies mai entren com a text lliure dins SQ.
- Duplicats eliminats pel hash de regla i paràmetres normalitzats.

## Costos congelats metodològicament

Com que encara s'acumulen captures, es congela la fórmula, no un número optimista:

- base: màxim entre p50 observat i 5 bps;
- conservador: màxim entre p95, 2×p50 i 8 bps;
- estrès: màxim entre 2×p95 i 15 bps;
- XAU en esdeveniment macro: mínim 30 bps en estrès;
- rollover real per costat; crèdits positius limitats a zero en estrès;
- perturbació separada per diferències entre font històrica i Ostium.

Una estratègia negativa a 1× no es rescata amb leverage.

## Gates abans del holdout

- Train: benefici net positiu en tots els costos i PF base ≥1,15.
- Validació: PF base ≥1,20, PF estrès ≥1,05, expectativa d'estrès positiva.
- Drawdown ≤25%.
- Mínim 120/40 trades train/validació en M15; 30/12 en D1.
- ≥60% d'anys de validació positius.
- ≥70% de veïns de paràmetres positius.
- Walk-forward: mínim cinc folds i ≥65% positius.
- OOS: PF base ≥1,20, PF estrès ≥1,05 i drawdown ≤25%.
- Bootstrap de 10.000 camins, trades perduts, slippage, candles, DST, gaps,
  stop-first i liquidació.

## Límits de promoció

- Màxim vuit acceptats per hipòtesi i 48 abans de robustesa.
- Màxim dos per hipòtesi i 12 globals poden veure el holdout.
- Cartera final: màxim vuit, màxim dos per mercat i correlació preferida ≤0,65.
- Quatre és un objectiu, no una quota: `NO_CANDIDATE` és un resultat vàlid.

## Següent check

El Check 5 compila els projectes/configuracions SQ, executa la generació amb
checkpoints recuperables i aplica els gates sense modificar aquest fitxer.
