# EURUSD D1 — screen d’hipòtesis Alquímia v4

Aquest screen no demana a StrategyQuant que descobreixi qualsevol patró. Primer
prova, només sobre el 50% de train, tres mecanismes econòmics diferents. SQ
només rebrà les famílies que sobrevisquin costos i estabilitat local.

## Contracte temporal i d’evidència

- Font: CSV canònic `EURUSD_ALQ_NY17_D1`, sessions Nova York 17:00.
- El trace conserva ruta absoluta, SHA-256, files totals, files de train i data
  final de train.
- El tall és posicional i preregistrat: `floor(files × 50%)`; no depèn del
  rendiment.
- Tota entrada usa informació disponible al tancament anterior i s’executa a
  l’obertura següent. Tota sortida ha de ser anterior o igual al final de train.
- El productor es nega a calcular rendiment fins que el model d’execució
  d’Ostium tingui `PASS_COSTS_FROZEN`.
- Una sola posició per variant; no hi ha trades solapats ni piramidació.

## Famílies preregistrades

| Família | Lògica | Central | Veïns locals |
|---|---|---|---|
| `d1_breakout` | Repricing persistent després de sortir d’un rang | breakout 55 dies, hold 15, stop 2,5 ATR | lookback 45 i 65 |
| `d1_momentum` | Persistència de tendències monetàries de termini mitjà | momentum 90 dies, hold 20, stop 3 ATR | lookback 75 i 105 |
| `d1_shock_reversion` | Normalització d’un shock curt de liquiditat | moviment 1,5 ATR, hold 5, stop 2 ATR | shock 1,25 i 1,75 ATR |

Cada veí canvia exactament un paràmetre. Per tant, els dos veïns requerits pel
gate mesuren una petita regió estable, no tres idees independents escollides
després de veure resultats. La graella inicial consumeix nou intents dels 5.000
permesos.

## Simulació

El senyal es calcula al tancament de la sessió `t`; l’entrada és l’open de
`t+1`. El stop ATR queda fixat amb informació de `t`. Si hi ha gap a través del
stop, s’utilitza l’open advers, no el preu teòric del stop. La sortida temporal
és l’open després del nombre de barres preregistrat. Els resultats són retorns
bruts; el gate resta després fee, impacte, oracle fix i rollover congelats.

Aquest screen és un filtre barat d’hipòtesis. Un `PASS` no és evidència
d’estratègia rendible: només autoritza que StrategyQuant generi implementacions
limitades d’aquella família i que després passin validació temporal, Monte
Carlo, compte de 200 USDC, holdout únic, traducció Python, paritat i paper.
