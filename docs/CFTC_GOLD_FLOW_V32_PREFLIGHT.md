# Preflight CFTC Gold flow v32

## Decisió

`BLOCK_RELEASE_LEDGER`. La font, l’esquema i la identitat Gold passen, però no es
pot definir ni provar una regla històrica fins reconstruir quan cada observació
era realment pública. No s’ha accedit a rendiment XAU, no hi ha regla, no s’ha
usat SQCLI i cap període de validació/OOS/holdout ha estat consultat.

## Font oficial

La CFTC descriu els Commitments of Traders com un desglossament de l’open interest
de dimarts. Normalment els publica divendres a les 15:30 ET, després de tres dies
de processament, però festius i incidències poden canviar la data:

- [CFTC — Commitments of Traders](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)
- [CFTC — calendari de publicació](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)
- [CFTC — històrics comprimits](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)
- [CFTC — anuncis especials històrics](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)

La categoria escollida és `Disaggregated Futures Only`. Permet separar producers,
swap dealers, managed money i altres reportables. Encara no s’ha triat cap camp
com a senyal.

## Comprovació reproduïble

S’han inspeccionat tres ZIP oficials, desats temporalment sota `lab/out/` i
verificats per SHA-256:

| Any | Reports Gold | Primer | Últim | Camps | Identitat |
|---:|---:|---:|---:|---:|---|
| 2010 | 52 | 05/01 | 28/12 | 191 | PASS |
| 2018 | 53 | 02/01 | 31/12 | 191 | PASS |
| 2026 parcial | 31 | 06/01 | 04/08 | 191 | PASS |

Identitat exacta als tres:

- Mercat: `GOLD - COMMODITY EXCHANGE INC.`
- CFTC contract market code: `088691`
- Commodity code: `088`

No hi ha dates duplicades, valors de posició negatius ni camps obligatoris
absents. El parser accepta les dues capçaleres de data observades. El 2018 conté
reports de dilluns 24 i 31 de desembre: no és lícit assumir que totes les files
corresponen a un dimarts normal.

## Per què encara queda bloquejat

La CFTC diu explícitament que no ofereix una llista completa de dates històriques
de publicació. Els anuncis oficials documenten excepcions materials:

- shutdown 2018–2019: publicació setmanal suspesa;
- incident ION de 2023: reports acumulats publicats posteriorment;
- interrupció 2025: diverses observacions es van publicar setmanes després.

Per tant, usar `report_date + 3 dies` o fins i tot una setmana fixa faria servir
informació que en alguns períodes encara no existia públicament. Tampoc és correcte
eliminar aquestes setmanes després d’haver mirat rendiment.

## Únic pas admissible

Construir un ledger versionat `report_date → actual_publication_at`, amb fonts
oficials per a totes les excepcions, i preregistrar abans de rendiment què es fa
quan la data no és demostrable: retard conservador justificat o exclusió. En live,
la disponibilitat s’ha de registrar amb el timestamp de la descàrrega efectiva,
mai deduir-la de la data del report.
