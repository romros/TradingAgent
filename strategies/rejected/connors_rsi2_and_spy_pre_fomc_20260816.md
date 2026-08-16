# Connors RSI(2) recent i SPY pre-FOMC — rebutjos 2026-08-16

## Connors RSI(2)

Es va mantenir exactament la regla coneguda: `Close>SMA(200)`, Wilder RSI(2)<5,
entrada al següent open i sortida al següent open després de `Close>SMA(5)`.
No es va cercar cap llindar. El bloc cronològicament nou 2025–29/05/2026 sobre
AAPL, JPM i SPY va superar el gate estadístic brut: 23 trades, +10,90%, PF
2,054 i DD 2,94%; AAPL i SPY eren positius.

Amb 2.000 USD, tres sleeves fixos, unitats senceres i costos IBKR d'estrès,
només s'executen 19 trades i el resultat és **−21,26 USD (−1,06%), PF 0,740**.
Només SPY queda positiu. No es pot seleccionar SPY després de veure aquest
resultat: seria selecció post hoc. Decisió `REJECT_SMALL_ACCOUNT_COST_GATE`.

## SPY pre-FOMC

Es van provar dues implementacions materialment diferents, totes dues
preregistrades i sense variants:

1. MOC anterior → MOC del dia FOMC: train −157,01 USD; validació+OOS
   −75,03 USD, PF 0,755. Rebutjada.
2. Efecte acadèmic M1: close de la barra 14:00 NY del dia anterior → close
   13:59 NY abans del comunicat. Es van validar 2.272 sessions de 390 minuts.
   Train −137,74 USD; validació 2022–2023 +82,91 USD; OOS 2024 −3,75 USD.
   Només 2022 és positiu; combinat PF 1,962 però `t=1,241`, per sota del gate
   1,645, i falla train/OOS/anys positius. Decisió `REJECT_TRUE_PRE_FOMC_GATE`.

La bona finestra de 2022 no justifica crear un filtre de règim retrospectiu.
Cap d'aquestes famílies entra a la llibreria, SQ, paper o LIVE.
