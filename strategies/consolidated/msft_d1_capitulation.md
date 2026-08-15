# MSFT D1 Capitulation

## Contracte executable

- Actiu: Microsoft (`MSFT`), timeframe D1.
- Direcció: només long; una posició simultània.
- Senyal sobre l'última barra tancada (`shift=1`):
  `Close < 0.98 × Open` i `Close < BollingerLower(20, 2)`.
- Entrada: mercat a la barra següent.
- Sortida: després d'una barra (`ExitAfterBars=1`).
- Sense stop-loss, profit-target, trailing stop ni break-even.
- SQ natiu original: `ExitAtEndOfDay=true`, hora 15:30. Aquest detall forma
  part de l'artefacte verificat i s'ha de reproduir literalment abans de decidir
  si es normalitza a una semàntica D1 diferent.
- Spread, slippage, comissió i swap dins SQ: zero; costos aplicats després.

## Reconstrucció en StrategyQuant

La construcció determinista està codificada a
`lab/sq_bridge/build_msft_capitulation_sqx_v1.py`.

1. Partir d'un SQX D1 compatible amb la mateixa versió SQ.
2. Executar el constructor amb `--template` i `--output`; aquest substitueix
   el senyal, fixa `ExitAfterBars=1`, elimina SL/PT i esborra resultats antics.
3. Retestar sobre la font MSFT certificada fins a 2024.
4. Exportar ordres i exigir exactament 67 dates d'entrada coincidents amb
   Python. No acceptar una coincidència només de PnL.
5. Aplicar l'economia del broker fora d'SQ i tornar a verificar qualsevol canvi
   d'horari o font.

## Evidència

- SQX reconstruïble: `data/ibkr_sq_v2/msft_capitulation_native/MSFT_CAPITULATION_D1_NATIVE_V1.sqx`.
- Contracte extret: `data/ibkr_sq_v2/msft_capitulation_native/extract_v1.json`.
- Paritat: 67 entrades esperades, 67 observades, dates exactes, a
  `data/ibkr_sq_v2/msft_capitulation_native/retest/run/signal_parity_receipt_v1.json`.
- Evidència de cartera:
  `data/ibkr_sq_v2/three_strategy_portfolio/sxr8_cat_msft_v1.json`.

## Limitacions

La font Python era ajustada i la font SQ nominal però consistent amb splits;
la paritat certificada és de senyals, no d'OHLC absolut. Els períodes històrics
no són un holdout nou completament verge. Recerca admesa; paper i LIVE no
autoritzats.

