#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EVENT_DATE=${FOMC_EVENT_DATE:?Set FOMC_EVENT_DATE as YYYY-MM-DD}
case "$EVENT_DATE" in
  20[0-9][0-9]-[01][0-9]-[0-3][0-9]) ;;
  *) echo "INVALID_FOMC_EVENT_DATE=$EVENT_DATE" >&2; exit 2 ;;
esac

NOW_DATE=$(TZ=America/New_York date +%F)
NOW_HHMM=$(TZ=America/New_York date +%H%M)
if [ "$NOW_DATE" != "$EVENT_DATE" ]; then
  echo "OUTSIDE_FOMC_DATE now_ny=$NOW_DATE event_date=$EVENT_DATE"
  exit 0
fi
if [ "$NOW_HHMM" -lt 1345 ] || [ "$NOW_HHMM" -gt 1645 ]; then
  echo "OUTSIDE_FOMC_WINDOW now_ny=$NOW_DATE-$NOW_HHMM window=1345-1645"
  exit 0
fi

EVENT_SLUG=$(printf '%s' "$EVENT_DATE" | tr -d '-')
EVIDENCE_DIR=${OSTIUM_EVENT_EVIDENCE_DIR:-$ROOT/data/ostium_event_economics/fomc_$EVENT_DATE}
SUMMARY="$EVIDENCE_DIR/xauusd_fomc_${EVENT_SLUG}_execution_summary_latest.json"
mkdir -p "$EVIDENCE_DIR"

OSTIUM_PAIR=XAU/USD \
OSTIUM_NOTIONALS=200,400,500,600 \
OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
  "$ROOT/scripts/capture_ostium_pair_economics.sh"

set -- "$EVIDENCE_DIR"/xauusd_ostium_execution_normalized_*.json
if [ ! -e "$1" ]; then
  echo "NO_NORMALIZED_EVENT_SNAPSHOTS" >&2
  exit 3
fi
python3 "$ROOT/lab/sq_bridge/fomc_event_execution_gate.py" "$@" \
  --event-date "$EVENT_DATE" --notionals 200,400,500,600 --output "$SUMMARY" >/dev/null
printf '%s\n' "$SUMMARY"
