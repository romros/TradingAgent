# SPY turn-of-the-month v1 — rebutjada pel gate estadístic

## Regla congelada

Una única regla publicada, sense optimització: long al tancament de la
penúltima sessió del mes i sortida al tancament de la tercera sessió del mes
següent. Això representa la finestra acadèmica −1…+3. Font: SPYUSUSD D1 RTH
Dukascopy sense dividends; la seva omissió és conservadora. Fricció d'estrès:
10 bps per round trip. El capital i el sizing no formen part d'aquest screen.

## Resultat sense obrir l'OOS 2024

| Període | Trades | Retorn net | PF net | DD net | t-stat brut |
|---|---:|---:|---:|---:|---:|
| Train 2017-05–2021 | 53 | +15,76% | 1,461 | 7,54% | 1,365 |
| Validació 2022–2023 | 23 | +3,92% | 1,266 | 4,81% | 0,674 |
| Combinat | 77 | +17,92% | 1,346 | 7,73% | 1,410 |

Hi ha un efecte econòmic coherent als dos blocs, però el t-stat combinat no
arriba al llindar unilateral preregistrat de 1,645. La decisió és
`REJECT_DEVELOPMENT`; 2024 continua sense consultar. No es poden provar altres
dies d'entrada o sortida per rescatar-lo: això seria tuning posterior al
resultat. Es pot conservar com a hipòtesi de diversificació, no com a quarta
estratègia amb edge validat.

Evidència reproduïble:

- `lab/sq_bridge/spy_turn_of_month_preregistration_v1.json`
- `lab/sq_bridge/spy_turn_of_month_screen_v1.py`
- `data/ibkr_sq_v2/spy_turn_of_month_v1/development.json`

