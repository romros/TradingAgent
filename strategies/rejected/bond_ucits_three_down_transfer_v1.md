# Bons UCITS — SMA200 + tres baixades + hold 10 rebutjada

Transferència exacta, sense buscar paràmetres, de la família multi-actiu
consolidada a dos ETF UCITS de Treasuries: IBTM i IDTL. La hipòtesi era que una
reversió curta de liquiditat podia diversificar la cartera d'accions.

Falla abans d'OOS i de qualsevol integració de cartera. El pooled train té 77
trades, −4,30% i PF 0,814. IBTM perd −16,60% al train i −1,63% a validació;
IDTL és positiu al train però produeix zero trades completats a validació. El
pooled de validació queda en −0,82% i PF 0,431. OOS 2024 no s'ha obert.

Evidència:
`data/ibkr_sq_v2/bond_ucits_three_down_transfer_v1/development.json`.
