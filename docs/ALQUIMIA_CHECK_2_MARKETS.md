# CHECK 2 — mercats no-cripto executables a Ostium

**Estat històric recalculat:** `PASS_RESEARCH_PARTIAL / 3 PAPER_INPUTS_READY`

> Aquest resultat només descriu l'auditoria Ostium tancada. No autoritza paper
> sota l'objectiu IBKR/SQCLI vigent.

**Evidència canònica:**
[`noncrypto_market_audit_v5.json`](../lab/sq_bridge/evidence/noncrypto_market_audit_v5.json)

## Què significa

- `PASS_RESEARCH_DATA_READY`: podem formular i provar estratègies teòriques sense
  haver consultat candidats o rendiments antics.
- `BLOCK_TECHNICAL_EVIDENCE`: falta una peça de dades abans de gastar SQCLI.
- `BLOCK_PAPER_INPUTS`: encara no hi ha prou captures d'execució per congelar
  costos; no impedeix recerca amb escenaris provisionals, però sí promoció.

## Resultat

| Mercat | Timeframe certificat | Recerca | Paper | Lectura planera |
|---|---:|---|---|---|
| EURUSD | D1 | PASS | INPUT READY | Històric 2003–31/07/2026, candles SQ i costos congelats; línia tancada |
| US500 | D1 | PASS | BLOCK | Històric canònic 2018–2026 i mapping D1 molt correlacionat; encara falta intradia certificat |
| USDJPY | M15 | PASS | INPUT READY | Històric 2007–2026, mapping M15 i costos congelats; línia tancada |
| GBPUSD | M15 | BLOCK | BLOCK | Font llarga acaba el 2023 i overlap reprèn el 2026: falta cobrir 2024–2025 |
| XAUUSD | M15 | PASS | INPUT READY | Històric 2007–2026, mapping M15 i costos congelats; línia tancada |

No s'ha llegit PnL, holdout ni cap candidat quantitatiu per seleccionar aquest
univers. Les proves antigues només aporten manifests i paritat tècnica.

## Qualitat de mapping destacada

- EURUSD D1: `PASS_CANDLE_PARITY` i font estesa fins al 31/07/2026.
- US500 D1: 77 sessions alineades, correlació de retorns 0,9988 i direcció 100%;
  la diferència close p95 és 10,34 bps i s'ha d'incloure a l'estrès.
- USDJPY M15: 656 barres completes, correlació 0,9961, direcció 98,45% i
  diferència close p95 de 0,92 bps.
- GBPUSD M15: el pilot recent té 2.071 barres i close p95 0,75 bps, però no
  repara el forat temporal de la font llarga.
- XAUUSD M15: 604 barres, correlació 0,9979, direcció 96,80% i close p95
  1,87 bps.

## Costos provisionals a 200 USDC de nocional

Són proxies de quote, no fills observats, i encara no estan congelats:

| Mercat | Mostres/dies | Cost round-trip p50 | p95 | Max leverage observat |
|---|---:|---:|---:|---:|
| EURUSD | 19 / 2 | 2,95 bps | 4,11 bps | 200× |
| USDJPY | 19 / 2 | 3,19 bps | 4,38 bps | 100× |
| GBPUSD | 19 / 2 | 3,41 bps | 4,37 bps | 200× |
| XAUUSD | 18 / 2 | 3,30 bps | 3,53 bps | 50× |
| US500 | 40 / 2 | 1,86 bps | 2,04 bps | pendent de congelar en el gate de sessió |

`bps` vol dir punts bàsics: 1 bp és 0,01% del nocional. Per exemple, 4 bps
sobre una posició de 1.000 USDC són aproximadament 0,40 USDC abans de rollover.

## Decisió per al Check 3

Primera biblioteca teòrica sobre:

1. XAUUSD M15 i USDJPY M15 com a nucli oportunista intradia;
2. EURUSD D1 i US500 D1 com a playbooks més lents i diversificadors;
3. GBPUSD només torna a entrar quan es tanqui el forat 2024–2025;
4. cap paper fins congelar costos i tornar a executar aquest auditor.

El Check 3 no reutilitzarà estratègies ni candidats antics. Formularà hipòtesis
noves abans de mirar performance.
