#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MARKER="# tradingagent-ostium-spx-economics"
DATA_DIR="$ROOT/data/ostium_economics"
LOG="$DATA_DIR/collector.log"
LOCK="/tmp/tradingagent-ostium-spx-economics.lock"
LINE="17 */2 * * 1-5 flock -n $LOCK env OSTIUM_EVIDENCE_DIR=$DATA_DIR $ROOT/scripts/capture_ostium_spx_economics.sh >> $LOG 2>&1 $MARKER"

mkdir -p "$DATA_DIR"
CURRENT=$(crontab -l 2>/dev/null || true)
if printf '%s\n' "$CURRENT" | grep -Fq "$MARKER"; then
  echo "already installed"
  exit 0
fi
{
  printf '%s\n' "$CURRENT"
  printf '%s\n' "$LINE"
} | crontab -
echo "$LINE"
