# Auditoria de completitud — Alquímia v3

**Objectiu:** metodologia pròpia per generar i seleccionar estratègies SQ
executables a Ostium amb 200 USDC, sense reutilitzar pipelines quantitatives
antigues més enllà d'exemples tècnics.

| Requisit | Evidència autoritativa | Estat |
|---|---|---|
| Metodologia pròpia versionada | `methodology_v3.json`, validada per `methodology.py` | PROVAT |
| Capital canònic 200 USDC | contracte v3 + verificador `CAPITAL_NOT_200` | PROVAT |
| SQ només genera candidats | principi `sq_role=candidate_generator_only` | PROVAT |
| Cap evidència quantitativa antiga | `legacy_quantitative_inputs=[]`; legacy només pot acabar en rebuig | PROVAT |
| Projecte SQ nou i reproduïble | CFX + manifest amb hashes, perfil i split segellat | PROVAT |
| Hipòtesi semàntica, no només blocs | gate AST sweep/reclaim | PROVAT AMB SQX REAL V5 |
| Llinatge immutable de candidats | rebuts encadenats, hash d'artefacte i subset obligatori | PROVAT AMB TESTS I CONTROL E2E |
| Holdout segellat | split/manifest + rebuig `EARLY_HOLDOUT` | PROVAT AMB TESTS |
| Semàntica dels artefactes per etapa | contracte estricte v2, camps i llindars verificats | PROVAT AMB CONTROL E2E; PENDENT EVIDÈNCIA REAL |
| Validació temporal SQ independent | rebut `temporal_validation` | CABLEJAT PROVAT; PENDENT CANDIDAT V3 REAL |
| Robustesa/Monte Carlo | rebut `robustness` | CABLEJAT PROVAT; PENDENT CANDIDAT V3 REAL |
| Economia Ostium 200 | rebut `small_account_economics` | CONTROL NEGATIU PROVAT; PENDENT PASS V3 |
| Traducció exacta Python | `sqx_extract` + `translation_exact` | CABLEJAT PROVAT; PENDENT CANDIDAT V3 REAL |
| Paritat DuckDB/BS/Ostium | rebut `parity_pass` | CABLEJAT PROVAT; PENDENT CANDIDAT V3 REAL |
| Paper | només després de tots els PASS | CONTROL NO PROMOCIONABLE PROVAT; PENDENT CANDIDAT REAL |
| Live | sempre autorització humana externa | PROVAT: v3 mai autoritza live |

## Controls executats

- Tests de manipulació de hash, canvi de candidat, salt d'etapa, holdout precoç,
  traducció aproximada i paritat absent.
- Contracte de cadena v2: cada JSON ha de declarar etapa, campanya, decisió,
  candidats, classe d'evidència i les mètriques mínimes pròpies de l'etapa. Una
  simple existència del fitxer ja no pot produir un PASS.
- Control sintètic determinista de 8/8 etapes a
  `lab/sq_bridge/evidence/alquimia_v3_strict_control`: `valid=true` i
  `operational_control_complete=true`, però obligatòriament
  `promotable=false`, `paper_ready=false` i `live_authorized=false`.
- Regressió completa del pont: 211 proves superades. També s'ha alineat una
  prova antiga amb el fee cripto conservador canònic de 10 bps del registre.
- XAU H4 R2 importat exclusivament com a control negatiu: cadena íntegra i
  terminal a economia de 200 USDC; no promocionable.
- V4 Builder nadiu: 20 SQX reals, 0/20 passen l'AST; rebuig terminal.
- V5 seed semàntic: smoke SQ real completat; preflight Dukascopy train-only de
  1.350 punts, 0 PASS d'estrès i 0 regions estables; rebuig terminal verificat.
- Validation, OOS i holdout v5 no s'han consultat.
- V6 XAU H1: 5.184 punts train i 0 regions estables; rebuig terminal.
- V7 congelada: discovery PASS però validació independent REJECT (PF estrès
  0,85); OOS i holdout no consultats. Cadena terminal verificada.
- V8 MSFT gap/shock: export D1 nadiu SQ verificat; close passa paritat recent,
  open/high/low fallen. `BLOCK` terminal al primer gate, abans de Builder.

La infraestructura metodològica i els seus bloquejos funcionen de punta a punta,
però l'objectiu global **encara no està complet**: falta que una candidata v3
real generada per StrategyQuant superi amb dades observades els gates fins a
paper. El control sintètic prova el cablejat; no prova cap edge ni rendiment.
