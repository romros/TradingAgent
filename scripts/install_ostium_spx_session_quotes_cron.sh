#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MARKER="# tradingagent-ostium-spx-session-quotes"
DATA_DIR="$ROOT/data/ostium_execution_quotes"
LOG="$DATA_DIR/collector.log"
LOCK="/tmp/tradingagent-ostium-spx-session-quotes.lock"
LINE="*/5 * * * 1-5 flock -n $LOCK $ROOT/scripts/capture_ostium_spx_session_quotes.sh >> $LOG 2>&1 $MARKER"

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
