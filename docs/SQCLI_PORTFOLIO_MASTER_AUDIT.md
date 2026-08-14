# SQCLI Portfolio Master — auditoria de capacitat

El 2026-08-14 s'ha executat un smoke disposable real amb SQX 143.2708. Portfolio
Master ha carregat dues estratègies natives, ha enumerat una combinació i ha
produït un SQX de cartera amb `dailyEquity.bin`, `orders.bin` i les dues parts
natives. Temps: 540 ms. Això prova automatització, no edge.

El control MSFT era una estratègia antiga no qualificada; queda prohibit usar el
seu rendiment. L'artefacte només demostra que la cadena CLI funciona.

Per auditar la cartera real SXR8 + CAT + MSFT cal:

1. conservar CAT 0.168 natiu;
2. reconstruir SXR8 turn-of-month i MSFT capitulation com SQX natius;
3. retestar cada regla amb els mateixos instruments, costos i 2022–2024;
4. exigir paritat trade a trade amb Python;
5. només llavors executar Portfolio Master i comparar equity, correlació,
   solapament i drawdown amb el motor Python.

Rebut: `data/ibkr_sq_v2/sq_portfolio_master_smoke/final_receipt.json`.
Resultat capability-only:
`data/ibkr_sq_v2/sq_portfolio_master_smoke/Portfolio_1_CAPABILITY_ONLY.sqx`.
