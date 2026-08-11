#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# US500/USD already has the denser dedicated two-hour collector.
PAIRS=${OSTIUM_RESEARCH_PAIRS:-"EUR/USD USD/JPY GBP/USD XAU/USD"}
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/data/ostium_economics_universe}
EURUSD_SUMMARY="$EVIDENCE_DIR/eurusd_ostium_execution_summary_latest.json"
EURUSD_PREFLIGHT="$EVIDENCE_DIR/eurusd_market_preflight_latest_v4.json"
EURUSD_SOURCE=${ALQUIMIA_EURUSD_D1_SOURCE:-/mnt/volume-SQ/user/imports/alquimia_eurusd_v4/EURUSD_ALQ_NY17_D1_V3.csv}
EURUSD_SCREEN_DIR=${ALQUIMIA_EURUSD_SCREEN_DIR:-$ROOT/data/alquimia_v4/eurusd-d1-alquimia-v4/screen-bootstrap}
STATUS=0

if OSTIUM_PAIRS="$PAIRS" OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
    "$ROOT/scripts/capture_ostium_economics_set.sh"; then
  :
else
  STATUS=1
fi

# Recompose the full EURUSD v4 preflight after every universe capture. It remains
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

# WAITING is read-only. On the first verified PASS this freezes every mutable
# `latest` input before evaluating train, and remains idempotent afterwards.
# It never starts SQCLI; successful hypotheses only receive generation plans.
if test -f "$EURUSD_PREFLIGHT"; then
  if PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.eurusd_v4_screen_trigger \
      --preflight "$EURUSD_PREFLIGHT" --source "$EURUSD_SOURCE" \
      --output-dir "$EURUSD_SCREEN_DIR"; then
    :
  else
    printf 'EURUSD_SCREEN_TRIGGER_FAILED preflight=%s\n' "$EURUSD_PREFLIGHT" >&2
    STATUS=1
  fi
else
  printf 'EURUSD_SCREEN_TRIGGER_SKIPPED missing=%s\n' "$EURUSD_PREFLIGHT" >&2
  STATUS=1
fi

exit "$STATUS"
