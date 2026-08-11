#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# US500/USD already has the denser dedicated two-hour collector.
PAIRS=${OSTIUM_RESEARCH_PAIRS:-"EUR/USD USD/JPY GBP/USD XAU/USD"}
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/data/ostium_economics_universe}
EURUSD_SUMMARY="$EVIDENCE_DIR/eurusd_ostium_execution_summary_latest.json"
EURUSD_PREFLIGHT="$EVIDENCE_DIR/eurusd_market_preflight_latest_v4.json"
EURUSD_SOURCE=${ALQUIMIA_EURUSD_D1_SOURCE:-/mnt/volume-SQ/user/imports/alquimia_eurusd_v4/EURUSD_ALQ_NY17_D1_V2.csv}
EURUSD_SCREEN_DIR=${ALQUIMIA_EURUSD_SCREEN_DIR:-$ROOT/data/alquimia_v4/eurusd-d1-alquimia-v4/screen-bootstrap}
STATUS=0

mkdir -p "$EVIDENCE_DIR"
for PAIR in $PAIRS; do
  if OSTIUM_PAIR="$PAIR" OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
      "$ROOT/scripts/capture_ostium_pair_economics.sh"; then
    PAIR_FROM=${PAIR%/*}
    PAIR_TO=${PAIR#*/}
    SLUG=$(printf '%s' "$PAIR_FROM$PAIR_TO" | tr '[:upper:]' '[:lower:]')
    SUMMARY="$EVIDENCE_DIR/${SLUG}_ostium_execution_summary_latest.json"
    COSTS="$EVIDENCE_DIR/${SLUG}_costs_latest_v4.json"
    PAIR_ID=$(python3 -c \
      'import json,sys; print(json.load(open(sys.argv[1]))["instrument"]["pair_id"])' \
      "$SUMMARY")
    if PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.ostium_small_account_cost_gate_v4 \
        --summary "$SUMMARY" --output "$COSTS" --pair-id "$PAIR_ID" \
        --pair-from "$PAIR_FROM" --pair-to "$PAIR_TO" >/dev/null; then
      :
    else
      printf 'COST_GATE_REFRESH_FAILED pair=%s\n' "$PAIR" >&2
      STATUS=1
    fi
  else
    printf 'CAPTURE_FAILED pair=%s\n' "$PAIR" >&2
    STATUS=1
  fi
done

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
