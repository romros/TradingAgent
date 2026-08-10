# Ledger de disponibilitat CFTC Gold v33

## Decisió

`PASS_CONSERVATIVE_LEDGER`. S'han congelat els arxius anuals oficials 2010–2026
i s'ha construït un ledger per report sense consultar cap preu o rendiment XAU.
Aquest pass només desbloqueja la definició prèvia d'una regla de flux; no valida
cap estratègia ni autoritza SQ, paper o live.

## Política temporal

La CFTC indica que el COT normalment es publica divendres a les 15:30 ET, sobre
posicions del dimarts anterior, i que els festius poden retardar-lo un o dos dies.
Com que la mateixa CFTC diu que no conserva una llista històrica completa de dates
de publicació, el ledger usa una disponibilitat conservadora de **report date + 7
dies, 15:30 America/New_York**.

Fonts oficials:

- [CFTC — COT i disponibilitat històrica](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)
- [CFTC — anuncis especials](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)
- [CFTC — shutdown 2018–2019](https://www.cftc.gov/PressRoom/PressReleases/7864-19)

## Exclusions preregistrades

- 24/12/2018–05/03/2019: shutdown i recuperació seqüencial;
- 26/03/2019: correcció posterior específica de CMX Gold;
- 31/01/2023–14/03/2023: incident ION i backlog;
- 30/09/2025–16/12/2025: lapse d'apropiacions i backlog.

S'exclouen completament en lloc d'inferir timestamps favorables. La regla de set
dies és més tardana que la publicació normal i els retards festius declarats; no
pretén reconstruir una falsa precisió intradia.
