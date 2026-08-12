# Alquímia — checkpoints de progrés

> **FULL DE RUTA HISTÒRIC TANCAT (2026-08-11).** No continuar aquests checks.
> El checkpoint actiu i l'ordre de lectura són a
> [`CURRENT_OBJECTIVE.md`](../CURRENT_OBJECTIVE.md).

Aquest document és el contracte de seguiment comprensible del projecte. Cada
fase acaba amb un resum per a l'operador abans d'obrir la següent fase important.
Cap resultat de recerca autoritza paper o live automàticament.

## Regles de comunicació i decisió

- Abans de cada check: explicar objectiu, entrada necessària i què es considerarà fet.
- Després de cada check: informar `PASS`, `PARTIAL` o `BLOCK`, evidència, problema
  pendent i següent proposta.
- No canviar sense explicar-ho: univers de mercats, capital, risc, leverage,
  nombre d'estratègies, gates, holdout o ús de paper/live.
- Les decisions tècniques reversibles es poden executar dins del check anunciat;
  qualsevol canvi material necessita un nou check visible.
- L'operador pot demanar `estat` en qualsevol moment i rebrà aquesta mateixa
  llista actualitzada, no només logs tècnics.

## Full de ruta

| Check | Resultat exigible | Estat inicial |
|---|---|---|
| 1. Requisits | Només no-cripto; capital inicial 200–500; fita 1.000; 4–8 estratègies; paper ≤14 dies | PASS |
| 2. Mercats | 4 research-ready; GBPUSD bloquejat; costos/paper encara bloquejats | PASS PARCIAL |
| 3. Hipòtesis | 6 famílies noves, contextuals i falsificables; sense performance | PASS |
| 4. Preregistre SQ | Segell v5: 6 famílies, 76.800 avaluacions, 48→12 candidats màxim | PASS |
| 5. Validació | OOS, walk-forward, Monte Carlo, veïnat, estrès i costos sense gates relaxats | EN CURS: preflight PASS |
| 6. Compte petit | Comparació 200/300/400/500/1.000, sizing, leverage, compounding i ruta a 1.000 | PENDENT |
| 7. Selecció teòrica | Fins a 4–8 supervivents complementàries, o `NO CANDIDATE` justificat | PENDENT |
| 8. Context i handoff | Replay del consell agentiu, paritat SQ↔Python↔Ostium i paper ≤14 dies | PENDENT |

## Format de cada informe de check

```text
CHECK N — NOM
Estat: PASS | PARTIAL | BLOCK
Què s'ha comprovat:
Què hem après:
Què no està resolt:
Decisió que es demana a l'operador (si n'hi ha):
Següent check proposat:
```

## Definició de final

La fase teòrica acaba només quan el Check 7 produeix una cartera que supera els
gates congelats o un informe `NO CANDIDATE`. El projecte complet no es considera
live-ready fins superar també el Check 8 i obtenir autorització humana explícita.

## Estat intern del Check 5

- Preflight: SQX 143.2708, llicència trial vigent en el moment de la prova i càrrega de dades, `PASS`.
- Pla cec: 18 feines i 76.800 avaluacions exactes, `PASS`.
- No s'ha executat cap projecte ni s'ha obert validació, OOS o holdout.
- Paritat exacta dels sis senyals Python ↔ `ChartData` de SQ: 5.040
  comparacions, zero diferències, `PASS`.
- Porta actual: compilar els sis building blocks i els 18 projectes `.cfx`,
  mantenint TP, SL i temps màxim fixos per plantilla de sortida.
- Els 18 exits, inclosos els gestors estructurals, estan implementats amb
  `STOP_FIRST`, stop que només s'estreny i sortida temporal sense inspeccionar
  intrabar la barra on ja s'ha sortit a l'obertura.
- Screen train v5 definitiu: 297 combinacions; una supervivient EURUSD D1
  (`+32,5%`, `PF 1,236`, `DD 8,79%`, 287 trades).
- Validació congelada 2018–2021: la supervivient falla (`PF 0,852`,
  retorn base `-4,27%`, 1/4 anys positius i 0/8 veïns positius).
- Decisió de la campanya v5: `NO CANDIDATE`; OOS i holdout romanen tancats i
  no es permet retuning de la candidata rebutjada.

## Campanya v6

- Preregistre nou, sense reutilitzar candidates v5, segellat amb SHA-256
  `86ed64eb08b05654d989110e9f4ebd1f76a974f41e0337e9a184c70d5b60a9bb`.
- 5 famílies noves i 153 combinacions train executades.
- Zero combinacions superen train; validació, OOS i holdout no s'obren.
- Millors PF intradia: XAU failed-shock `0,741`, XAU London failure `0,777`,
  USDJPY breakout `0,542`, USDJPY failure `0,352`.
- EURUSD exhaustion té rendiment positiu màxim però només 7 trades, lluny dels
  30 mínims.
- Decisió: `NO CANDIDATE`. No iniciar v7 sobre les mateixes dades sense nova
  evidència o un univers/històric materialment nou.
