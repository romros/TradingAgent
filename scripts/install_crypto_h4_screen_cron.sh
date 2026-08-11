#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MARKER="# tradingagent-crypto-h4-screen-v4"
DATA_DIR="$ROOT/data/ostium_economics_universe"
RUNTIME_DIR="/mnt/volume-SQ/user/alquimia_runtime/crypto_h4_screen_v4"
LOG="$DATA_DIR/crypto-h4-screen-worker.log"
LOCK="/tmp/tradingagent-crypto-h4-screen-v4.lock"
LINE="3,13,23,33,43,53 * * * * flock -n $LOCK env OSTIUM_EVIDENCE_DIR=$DATA_DIR ALQUIMIA_CRYPTO_SCREEN_STATE_DIR=$RUNTIME_DIR $ROOT/scripts/run_crypto_h4_screen_workers.sh >> $LOG 2>&1 $MARKER"

mkdir -p "$DATA_DIR" "$RUNTIME_DIR"
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
