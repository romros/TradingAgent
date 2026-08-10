# Ostium — model de liquidació Alquímia v4

## Contracte

Alquímia v4 usa `ostium_threshold_cost_buffered`. No declara
`ostium_exact`, perquè un backtest de candles no pot provar el timing exacte
d'un keeper ni un fill intrabar.

Per leverage `L` i màxim del parell `Lmax`, la distància nominal percentual del
preu és:

```text
loss_threshold_pct = 100 - 25 × L / Lmax
nominal_distance_pct = loss_threshold_pct / L
```

La documentació d'Ostium publica el mateix llindar: a 200x sobre un parell de
200x, una pèrdua aproximada del 0,375% consumeix el 75% permès; a 20x, la
distància és aproximadament 4,875%.

El backtest redueix aquesta distància amb una erosió conservadora:

```text
execution_erosion_pct = stress_roundtrip_bps / 100
carry_erosion_pct = stress_annual_cost_pct(side) × days_to_MAE / 365.25
effective_distance_pct = max(0,
    nominal_distance_pct - execution_erosion_pct - carry_erosion_pct)
```

S'utilitza el round-trip estressat complet abans de la MAE tot i que una
liquidació pot succeir abans de tancar. És deliberadament advers: cobreix fee,
oracle d'estrès i impacte sense reclamar que coneixem el repartiment intrabar.

Cada run Monte Carlo ha d'aportar:

- `maximum_adverse_excursion_pct` calculada sobre retorn brut;
- `maximum_adverse_excursion_side` (`long` o `short`);
- `maximum_adverse_excursion_holding_days`;
- resultats agregats i exposició per recomputar costos.

Una run compta com liquidada quan `MAE >= effective_distance_pct`. El compte
petit aplica la pitjor erosió observada de tots els seus trades a cada punt de
la graella 1–200x, abans d'exigir un buffer liquidació/stop ≥1,5.

## Evidència primària

- Ostium explica llindars, exemples per leverage i que el rollover acosta la
  liquidació: <https://docs.ostium.com/traders/trading/liquidation>
- El contracte calcula el col·lateral després de marge de liquidació, rollover
  i funding:
  <https://github.com/0xOstium/smart-contracts-public/blob/8390ce497f68fb128900840e0ec30683afa945d3/src/OstiumPairInfos.sol#L811-L817>
- El valor final resta rollover i funding del col·lateral i PnL:
  <https://github.com/0xOstium/smart-contracts-public/blob/8390ce497f68fb128900840e0ec30683afa945d3/src/OstiumPairInfos.sol#L859-L868>

## Límits

Aquest gate és apte per rebutjar leverage insegur, no per prometre que una ordre
stop sempre evitarà liquidació. Gaps, latència, keeper, discrepància intrabar i
fills pitjors continuen exigint paritat, paper trading i autorització humana.
