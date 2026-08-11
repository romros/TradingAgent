#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MARKER="# tradingagent-ostium-crypto-economics"
DATA_DIR="$ROOT/data/ostium_economics_universe"
LOG="$DATA_DIR/crypto-collector.log"
LOCK="/tmp/tradingagent-ostium-crypto-economics.lock"
LINE="17 * * * * flock -n $LOCK env OSTIUM_EVIDENCE_DIR=$DATA_DIR $ROOT/scripts/capture_ostium_crypto_economics.sh >> $LOG 2>&1 $MARKER"

mkdir -p "$DATA_DIR"
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
