#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# US500/USD already has the denser dedicated two-hour collector.
PAIRS=${OSTIUM_RESEARCH_PAIRS:-"EUR/USD USD/JPY GBP/USD XAU/USD"}
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/data/ostium_economics_universe}
EURUSD_SUMMARY="$EVIDENCE_DIR/eurusd_ostium_execution_summary_latest.json"
STATUS=0

mkdir -p "$EVIDENCE_DIR"
for PAIR in $PAIRS; do
  if OSTIUM_PAIR="$PAIR" OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
      "$ROOT/scripts/capture_ostium_pair_economics.sh"; then
    :
  else
    printf 'CAPTURE_FAILED pair=%s\n' "$PAIR" >&2
    STATUS=1
  fi
done

# Recompose the EURUSD v4 gate after every universe capture. It remains
# fail-closed until the 30 samples / 3 days / 6 UTC hours contract matures.
if test -f "$EURUSD_SUMMARY"; then
  if OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
      "$ROOT/scripts/refresh_eurusd_v4_preflight.sh"; then
    :
  else
    printf 'PREFLIGHT_REFRESH_FAILED pair=EUR/USD\n' >&2
    STATUS=1
  fi
else
  printf 'PREFLIGHT_REFRESH_SKIPPED missing=%s\n' "$EURUSD_SUMMARY" >&2
  STATUS=1
fi

exit "$STATUS"
