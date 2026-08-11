# Alquimia SQ custom blocks v4

This directory is the version-controlled source of experimental StrategyQuant
extensions.  It is not an installed production snippet bundle.

`parity/AlquimiaATRParityHarness.java` bypasses SQ 143's permissive Indicator
Tester result threshold.  It uses the real SQ `ChartData` and `DataSeries`
classes and requires bit-for-bit equality with every Python oracle value.
The isolated harness includes an empty `MersenneTwisterRng` constructor stub:
SQDataLib instantiates that application-only cache dependency at startup, but
the tested series and ATR path never invokes it.

## Semantic contract

`AlquimiaH4GapSafeSMAATR` must match
`crypto_h4_gap_safe_atr_v4.gap_safe_sma_atr`:

- exact expected spacing: 14,400,000 milliseconds;
- true range resets to `high-low` on the first bar after a gap;
- arithmetic mean of exactly 14 consecutive true ranges;
- no warm-up value before 14 consecutive bars;
- no imputation and no Wilder recurrence.

The SLPT formula evaluates shift 1 because a market entry is placed on the bar
after the decision.  It intentionally does not apply SQ's native six-decimal
ATR rounding: the canonical Python stop uses the full SMA value.  The
continuity condition takes a transition count; a signal lookback of `N` bars
requires `N` transitions from its endpoint to its comparison bar.

Signal lookbacks also need a separate continuity guard.  An open trade that
later crosses a missing-data interval cannot be removed by an ordinary SQ
strategy rule without future knowledge.  Exact evaluation therefore requires
running each continuous source segment independently and aggregating the
trades.  Until that segmented runner is verified, these blocks do **not**
authorize strategy promotion and SQ remains proposal-generation-only.

The four `SQ/Blocks/Alquimia` condition blocks bind signal period and gap
validation inside one generated node.  They also require the 14-bar ATR window
at the signal endpoint to be continuous, matching Python's signal eligibility.
`AlquimiaSignalParityHarness` evaluates them with SQ's real shifted series at
the next-bar entry event against Python expectations for multiple periods,
shifts and ROC levels, including windows around a real Dukascopy data gap.

The deterministic compile-only builder is
`crypto_h4_custom_block_build_v4.py`.  Its receipt deliberately reports
`promotion_authorized=false`; compilation is not numeric parity.

`crypto_h4_continuous_segments_v4.py` creates the independent source segments
needed to avoid future-looking gap handling.  No segment is silently discarded;
short segments are retained and marked ineligible in the manifest.
