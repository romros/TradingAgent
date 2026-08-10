#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# US500/USD already has the denser dedicated two-hour collector.
PAIRS=${OSTIUM_RESEARCH_PAIRS:-"USD/JPY GBP/USD EUR/USD XAU/USD"}
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/data/ostium_economics_universe}

mkdir -p "$EVIDENCE_DIR"
for PAIR in $PAIRS; do
  OSTIUM_PAIR="$PAIR" OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
    "$ROOT/scripts/capture_ostium_pair_economics.sh"
done

# Recompose the EURUSD v4 gate after every universe capture. It remains
# fail-closed until the 30 samples / 3 days / 6 UTC hours contract matures.
OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
  "$ROOT/scripts/refresh_eurusd_v4_preflight.sh"
