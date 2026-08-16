# GOOG i XOM D1 price-action SQ — rebutjades

Campanyes natives SQ, congelades abans de consultar performance. Totes dues van
usar 2017–2021 per discovery, 2022–2023 per validació i 2024 com a OOS segellat;
2025 no es va consultar. La cerca era long-only, màxim dues condicions, amb
SMA/EMA/RSI/ROC/ADX, SL/PT i sortida temporal. Els representants es van escollir
com a medoides de famílies estructurals repetides, no pel millor benefici.

## GOOG

SQ va trobar 60 candidats en 39 famílies. Es van validar vuit representants amb
unitats senceres i costos IBKR d'estrès sobre 1.000 USD. Cap va superar tots els
gates. `Strategy 0.33` va ser el millor diagnòstic (+15,15%, PF 1,275 i DD
14,34%), però només va estar activa en quatre trimestres i només dos van ser
positius. El 2024 no es va obrir.

Evidència: `data/ibkr_sq_v2/goog_d1_capitulation_pilot/validation_gate.json`.

## XOM

SQ va trobar 60 candidats en 32 famílies. Cinc dels vuit representants eren
implementables pel traductor; tres es van excloure abans de validació per
`NON_CLOSE_COMPUTED_FROM`. Dos candidats van passar 2022–2023. Es va congelar
un sol finalista, `Strategy 0.202`: +45,21%, 24 trades, PF 1,460 i DD 14,61%
sota estrès.

El 2024 OOS el va rebutjar: 11 trades, −1,42%, PF 0,947 i DD 10,47% sota
estrès. Amb costos tiered era +2,14%, però no compleix el contracte preregistrat
de retorn positiu i PF ≥1,10 sota estrès. No es retoca ni s'obre el segon
supervivent després de veure l'OOS.

Evidència: `data/ibkr_sq_v2/xom_d1_price_action_pilot/validation_gate.json` i
`data/ibkr_sq_v2/xom_d1_price_action_pilot/oos/0_202/small_account_audit.json`.

Cap de les dues campanyes autoritza paper o LIVE.
