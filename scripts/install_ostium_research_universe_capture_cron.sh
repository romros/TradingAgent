#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MARKER="# tradingagent-ostium-research-universe-economics"
DATA_DIR="$ROOT/data/ostium_economics_universe"
LOG="$DATA_DIR/collector.log"
LOCK="/tmp/tradingagent-ostium-research-universe-economics.lock"
LINE="37 */4 * * 1-5 flock -n $LOCK env OSTIUM_EVIDENCE_DIR=$DATA_DIR $ROOT/scripts/capture_ostium_research_universe_economics.sh >> $LOG 2>&1 $MARKER"

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
