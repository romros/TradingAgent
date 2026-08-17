# EEM D1 simple discovery v1 — rebutjada

## Veredicte

La campanya random de SQ sobre EEM no produeix cap família amb edge estadístic
fora de mostra. 2024 no s'ha obert i no s'ha optimitzat cap perdedor.

## Contracte i selecció

- Font ajustada: 2.012 barres D1, 2017-01-03 a 2024-12-31.
- Train visible a SQ: 2017–2021; validació: 2022–2023; OOS 2024 segellat.
- Long i short, màxim dues regles simples, 35 trades i PF 1,08 mínims al train.
- 488 generades, 100 conservades; 54 famílies estructurals.
- La selecció usa el medoid de famílies amb almenys dos membres. De vuit
  representants, sis són traduïbles i es congelen abans de validar.

## Resultats de validació a 1.000 USD

Economia: accions senceres, 1× capital, 1 USD mínim per ordre, 10 bps adversos
per costat i 3% anual conservador de préstec només pels shorts.

| Candidat | Trades | Long/short | Retorn stress | PF | Trimestres + | DD |
|---|---:|---:|---:|---:|---:|---:|
| 0.321 | 57 | 23/34 | −32,07% | 0,693 | 2 | 47,77% |
| 0.334 | 64 | 40/24 | −31,63% | 0,685 | 1 | 34,85% |
| 0.278 | 44 | 16/28 | −24,87% | 0,667 | 3 | 24,87% |
| 0.133 | 28 | 13/15 | −22,56% | 0,603 | 3 | 26,06% |
| 0.320 | 30 | 13/17 | −9,39% | 0,881 | 2 | 34,82% |
| 0.52 | 53 | 18/35 | −35,13% | 0,614 | 1 | 36,54% |

Cap candidat arriba a PF 1,15 ni a cinc trimestres positius. La família queda
al registre «no repetir» amb aquest actiu, univers de blocs i períodes.

Evidència: `data/ibkr_sq_v2/eem_d1_simple_discovery_v1/`. No autoritza paper
ni live.
