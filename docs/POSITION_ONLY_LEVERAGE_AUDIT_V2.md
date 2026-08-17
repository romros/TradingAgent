# Auditoria de palanquejament només amb posicions — quatre edges

## Decisió

La variant congelada de quatre sleeves de 1.000 USD, capital inicial de 2.000
USD i límit de broker 2x passa el gate històric 2022–2024. El préstec no es
carrega permanentment: es reconstrueix el saldo de caixa amb cada entrada i
sortida i només genera interessos quan la caixa és negativa.

| Escenari | Retorn net | Drawdown diari | Costos | Interessos |
|---|---:|---:|---:|---:|
| Tiered indicatiu | +69,02% | 14,92% | 100,09 USD | 13,89 USD |
| Fixed indicatiu | +60,21% | 15,49% | 271,50 USD | 18,70 USD |
| Estrès | **+56,04%** | **15,92%** | **351,82 USD** | **21,67 USD** |
| SPY buy-and-hold | +26,93% | 23,41% | comparador | — |

La caixa prestada màxima reconstruïda en estrès és 1.519,96 USD. L'equity
mínima és 1.776,03 USD. Hi ha 93 operacions: CAT 57, MSFT 15, JPM 20 i SGLN 1.

## Què s'ha corregit

- Portfolio Composer necessita pesos del 50% per sleeve sobre capital 2.000
  per aconseguir pressupost 1.000; `leverage=2` amb pesos del 25% era un no-op
  verificat i queda registrat a la preregistració v1.
- Les ordres s'han exportat separadament per membre: l'export del compost amb
  `data=main` només retornava CAT.
- SGLN no es tracta com si GBP fos USD. Amb ECB GBPUSD congelat compra 26
  unitats, no les 36 que mostra la comptabilitat neutral de SQ.
- El round-trip complet es carrega a l'entrada, una convenció conservadora.

## Interpretació correcta

És una evidència històrica prometedora i ara sí supera SPY sota l'escenari
d'estrès preregistrat. No prova rendiment futur, no incorpora fills reals d'un
compte IBKR i no autoritza ni paper ni LIVE. Tampoc demostra encara que superi
buy-and-hold dels mateixos quatre actius; aquesta és la següent comparació que
cal tancar abans de considerar-la configuració ideal.

## Evidència reproduïble

- `lab/sq_bridge/four_edge_position_leverage_native_preregistration_v2.json`
- `lab/sq_bridge/four_edge_position_leverage_audit_v2.py`
- `lab/sq_bridge/test_four_edge_position_leverage_audit_v2.py`
- `data/ibkr_sq_v2/four_edge_position_leverage_v1/net_audit_v2.json`
- `data/ibkr_sq_v2/four_edge_position_leverage_v1/Portfolio-1786963273774.sqx`

`paper_authorized=false` i `live_authorized=false`.
