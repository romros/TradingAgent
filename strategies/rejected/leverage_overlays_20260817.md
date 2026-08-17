# Overlays de leverage rebutjats — 17/08/2026

Aquest document conserva dues vies falsificades amb regles congelades. Cap
resultat autoritza shadow, paper o live.

## SPY SMA200 a 1,5×

Exposició 1,5× si el close anterior era superior a SMA200, 0× altrament;
canvi a l'open, 10 bps de rotació i 8% anual de finançament.

- Train: +65,60% contra +100,28% buy-and-hold.
- Validació 2022–2023: −10,54% contra +3,24%; DD 30,22% contra 24,50%.
- 2024: +33,27% contra +24,89%, però DD 12,65% contra 8,41%.

Decisió: `REJECT_RETURN_AND_DRAWDOWN_GATE`. No s'optimitzen SMA ni múltiple.

## Quatre edges amb leverage constant 2×

Overlay analític sobre CAT/MSFT/JPM/SGLN, costos d'estrès ja inclosos i 8%
anual sobre una unitat de capital prestada. El finançament es calcula per dies
naturals reals; una primera versió errònia tractava punts de cap de setmana
com sessions `/252` i fou substituïda abans d'interpretar el resultat.

- Activa: +10,42%, DD 19,89%.
- SPY: +26,93%, DD 23,41%.

Decisió: `REJECT_LEVERAGE_OVERLAY`. Pagar préstec sobre tota la cartera quan
les estratègies estan sovint en cash és ineficient. Això no falsifica encara
el leverage només mentre cada posició és oberta, que exigeix una reconstrucció
nativa separada amb sizing i finançament per trade.

## Evidència

- `data/ibkr_sq_v2/spy_sma200_levered_v1/screen_v1.json`
- `data/ibkr_sq_v2/four_edge_leverage_overlay_v1/screen_v1.json`
