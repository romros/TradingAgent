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

És una evidència històrica prometedora i supera SPY sota l'escenari d'estrès
preregistrat. No prova rendiment futur, no incorpora fills reals d'un compte
IBKR i no autoritza ni paper ni LIVE.

La comparació posterior amb els mateixos actius ja està tancada:

| Configuració | Retorn acumulat | CAGR | Drawdown |
|---|---:|---:|---:|
| Cartera activa | **+56,04%** | **16,00%** | **15,92%** |
| Buy-and-hold, 500 USD/actiu | +47,56% | 13,86% | 20,97% |
| Buy-and-hold, 1.000 USD/actiu a 2x | +76,15% | 20,79% | 45,26% |

L'activa supera la comparació sense palanquejament en retorn i risc. No supera
el retorn retrospectiu del buy-and-hold a exposició 2x, però evita una caiguda
del 45,26%. Això és una millora real de perfil risc/retorn, no una victòria
en retorn absolut contra qualsevol quantitat de palanquejament.

Per respectar unitats senceres, les sèries total-return ajustades s'escalen al
preu nominal negociable del primer dia. Això evita que el preu ajustat històric
fabriqui accions addicionals que mai no s'haurien pogut comprar.

## Evidència reproduïble

- `lab/sq_bridge/four_edge_position_leverage_native_preregistration_v2.json`
- `lab/sq_bridge/four_edge_position_leverage_audit_v2.py`
- `lab/sq_bridge/test_four_edge_position_leverage_audit_v2.py`
- `data/ibkr_sq_v2/four_edge_position_leverage_v1/net_audit_v2.json`
- `data/ibkr_sq_v2/four_edge_position_leverage_v1/Portfolio-1786963273774.sqx`
- `lab/sq_bridge/four_edge_same_assets_buy_hold_v1.py`
- `data/ibkr_sq_v2/four_edge_position_leverage_v1/same_assets_buy_hold_v1.json`

`paper_authorized=false` i `live_authorized=false`.
