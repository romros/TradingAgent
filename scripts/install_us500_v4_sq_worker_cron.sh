#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MARKER="# tradingagent-us500-v4-sq-worker"
STATE_DIR="$ROOT/data/alquimia_v4/us500-d1-alquimia-v4/sq-worker"
LOG="$STATE_DIR/worker.log"
LOCK="/tmp/tradingagent-us500-v4-sq-worker.lock"
LINE="*/10 * * * 1-5 flock -n $LOCK $ROOT/scripts/run_us500_v4_sq_worker.sh >> $LOG 2>&1 $MARKER"

mkdir -p "$STATE_DIR"
CURRENT=$(crontab -l 2>/dev/null || true)
if printf '%s\n' "$CURRENT" | grep -Fxq "$LINE"; then
  echo "already installed"
  exit 0
fi
{
  printf '%s\n' "$CURRENT" | grep -Fv "$MARKER" || true
  printf '%s\n' "$LINE"
} | crontab -
echo "$LINE"
