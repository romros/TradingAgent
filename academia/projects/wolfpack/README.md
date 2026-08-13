# Wolfpack

Motor d'intel·ligència de mercat per convertir dades de venues, comportament de
traders i règims en situacions explicables. És un projecte separat dins
`academia/`: reutilitza evidència i política, però no executa trading ni modifica
StrategyQuant.

## Objectiu

Trobar informació que millori prospectivament decisions per a un compte de 500
USDC a Ostium. Una wallet guanyadora és una font potencial, no una estratègia.

## Flux

```text
diari de venues + fills públics + règim
                 ↓
           fets normalitzats
                 ↓
   Caçador → Fiscal → Gestor de risc
                 ↓
C0 dada / C1 anomalia / C2 hipòtesi / C3 paper
```

`C4 candidat operable` i `C5 autoritzat` no es poden generar fins que una versió
futura incorpori els gates prospectius i una autorització explícita. La versió
actual té sostre `C1` sense mostra i `C2` amb una cohort suficient; mai recomana
una entrada real.

## Ús

```bash
python3 academia/projects/wolfpack/wolfpack.py brief \
  --diary /tmp/cross-venue-diary-forward-20260813.jsonl \
  --follows /tmp/ostium-follow-forward-20260813.jsonl \
  --output /tmp/wolfpack-brief.json
```

Les adreces i feeds crus no entren a Git. `pack.json` només conté hashes, estat i
competència demostrada. Els briefs diaris agregats es podran promocionar a
`academia/experiments/observations/` quan compleixin el protocol.

## Manteniment

- diàriament: generar brief i comprovar fonts/errors;
- setmanalment: descobrir candidats amb dades passades, sense alterar la cohort
  congelada de l'experiment actiu;
- cada 30 dies: degradar/promoure per regla preregistrada i comparar contra
  baselines sense llops;
- cada canvi de font: revalidar contracte, escala, oracle, fees i timestamps.

No cal un LLM per mantenir la capa factual. Quan s'afegeixi un consell d'IA,
rebrà un brief immutable i haurà de retornar els contractes de `council.json`;
cap model podrà modificar mètriques o saltar el sostre de criticitat.

