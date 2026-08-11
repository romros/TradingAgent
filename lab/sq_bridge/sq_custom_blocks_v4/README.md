# Alquimia SQ custom blocks v4

This directory is the version-controlled source of experimental StrategyQuant
extensions.  It is not an installed production snippet bundle.

## Semantic contract

`AlquimiaH4GapSafeSMAATR` must match
`crypto_h4_gap_safe_atr_v4.gap_safe_sma_atr`:

- exact expected spacing: 14,400,000 milliseconds;
- true range resets to `high-low` on the first bar after a gap;
- arithmetic mean of exactly 14 consecutive true ranges;
- no warm-up value before 14 consecutive bars;
- no imputation and no Wilder recurrence.

Signal lookbacks also need a separate continuity guard.  An open trade that
later crosses a missing-data interval cannot be removed by an ordinary SQ
strategy rule without future knowledge.  Exact evaluation therefore requires
running each continuous source segment independently and aggregating the
trades.  Until that segmented runner is verified, these blocks do **not**
authorize strategy promotion and SQ remains proposal-generation-only.

The deterministic compile-only builder is
`crypto_h4_custom_block_build_v4.py`.  Its receipt deliberately reports
`promotion_authorized=false`; compilation is not numeric parity.
