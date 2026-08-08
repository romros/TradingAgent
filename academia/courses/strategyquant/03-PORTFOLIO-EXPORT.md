# Tram 3 — Cartera, exportació i paritat

## Portfolio Composer

Una cartera no rescata estratègies dolentes. Només hi entren components que ja
han superat els gates individuals. La pregunta és si cada candidat aporta edge o
risc diferent quan coincideixen posicions, no si redueix una correlació mitjana.

Comprovar:

1. alineació temporal de trades i dades;
2. exposició simultània per instrument, direcció i factor de risc;
3. correlació en trams adversos, no només global;
4. drawdown conjunt, tail loss i concentració de contribució;
5. free margin, ordres omeses i prioritat quan no caben totes;
6. costos i mida mínima després d'aplicar pesos;
7. estabilitat dels pesos en finestres i règims diferents.

Portfolio Composer (build 141+) recomputa position sizing segons pesos i simula
balance, leverage i free margin. El log d'ordres acceptades/omeses és evidència
obligatòria. Un pes «òptim» trobat sobre el mateix historial és una nova
optimització i necessita validació fora de la mostra usada per ponderar.

## Exportació

Conservar sempre l'artifact `.sqx`, pseudocodi/XML i codi exportat amb hashes.
Registrar build, engine, opció de paràmetres i money management. Canviar MM durant
l'export crea una variant, no una representació equivalent.

## Reconciliació cross-platform

Executar la mateixa finestra amb:

- mateix historial i timezone;
- mateixa construcció de bars i timeframe;
- motor corresponent a la plataforma;
- mateix spread, slippage, comissió, swap i sessions;
- mateix sizing, rounding i mínims;
- mateix ordre d'avaluació de stop/target i regles.

Comparar primer cada trade: timestamp, costat, entry, exit, size, stop/target i
motiu. Comparar PnL agregat abans de conciliar trades amaga compensacions. La
sortida és `PARITY_PASS`, `CONFIG_MISMATCH`, `ENGINE_DIFFERENCE` o
`UNEXPLAINED_DIFFERENCE`; només la primera permet avançar.

Per Ostium o un motor propi, exportar pseudocodi/XML no autoritza implementar ni
executar trading. Primer es crea una especificació independent i una prova de
paritat fora d'Academia.

Fonts: `sq_official_portfolio_composer_20241015`,
`sq_official_source_code_export_20200522` i
`sq_official_crossplatform_reliability_20190429`.

## Compounding i leverage amb compte petit

Dimensionar primer per risc: `notional = equity × risk_pct / stop_distance_pct`.
Després calcular el collateral com `notional / leverage`. Augmentar leverage redueix
marge requerit però no pot augmentar el nocional decidit pel risc. A cada entrada
cal recomputar equity realitzada, free margin, risc simultani i leverage efectiu.

La comparació activa 3-vs-5 ha d'usar el mateix univers congelat i simular ordres omeses. TLT queda fora fins que existeixi una història negociable autoritzada; DGS20 només pot etiquetar règims.
Cinc actius no són més diversos si comparteixen driver o si les comissions fixes i
el marge impedeixen executar-los. El manifest inicial és
`experiments/pending/ostium-500-portfolio-3v5-v1.json`. El manifest 3-vs-6 anterior es conserva com a traça de la decisió, no com a experiment actiu.

Abans del Builder, executar `audit_portfolio_data.py` contra una còpia de només
lectura del catàleg SQ. Una coincidència de nom i dates només autoritza preparar
projectes: encara falten gaps, sessions, timezone i provenance. Si un actiu no hi
és, no substituir-lo després de veure resultats; revisar l'univers o adquirir dades
com una nova decisió preregistrada.
