# XAU/USD CFTC Managed Money v34

## Decisió

`REJECT_NO_SQ`. La freqüència i la simetria del senyal són adequades, però els
quatre punts preregistrats per a rendiment perden fins i tot abans de costos en
train 2010–2017. Validació 2018–2020, OOS 2021–2023 i holdout 2024–2026 continuen
segellats. No s'ha utilitzat SQCLI.

## Hipòtesi provada

Continuació d'una variació gran del net de `Managed Money` de futurs Gold,
normalitzat per open interest. La dada només es considera disponible segons el
ledger conservador v33. El grid finit tenia 27 punts: lookback 2/4/8 setmanes,
llindar 1/2/3 punts percentuals i hold 1/2/4 setmanes, amb una sola posició.

El gate sense preus va deixar un centre estable (`2, 3, 1`) i els tres veïns
necessaris per comprovar estabilitat econòmica. El centre tenia 219 senyals de
freqüència, 113 long i 106 short, repartits pels vuit anys.

## Resultat train

| Lookback / llindar / hold | Trades executats | PnL brut | PF base | EV base | PnL base | PF estrès | PnL estrès |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 / 2 / 1 | 281 | −18,02 | 0,686 | −0,191 | −53,74 | 0,459 | −109,85 |
| 2 / 3 / 1 | 217 | −13,23 | 0,697 | −0,188 | −40,80 | 0,471 | −84,18 |
| 2 / 3 / 2 | 127 | −13,51 | 0,730 | −0,235 | −29,88 | 0,469 | −71,43 |
| 4 / 3 / 1 | 266 | −17,85 | 0,678 | −0,194 | −51,70 | 0,454 | −104,76 |

Imports en USDC amb capital 200, nocional 60, leverage venue 14x i exposició
efectiva 0,3x. No hi ha liquidacions. El punt central només té 2/8 anys positius
en base i 0/8 a estrès; les dues direccions perden.

## Interpretació

No és un problema que es pugui arreglar amb apalancament: l'expectativa és
negativa abans de costos. Invertir el senyal, eliminar una direcció, canviar
llindars o obrir períodes futurs després de veure el resultat seria una nova
hipòtesi seleccionada post hoc i queda prohibit per aquesta campanya.

La caché anual M15 creada per executar la prova és regenerable, versiona un
fingerprint dels M1 canònics i no és evidència de rendibilitat per si mateixa.
