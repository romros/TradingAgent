#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PAIRS=${OSTIUM_CRYPTO_PAIRS:-"BTC/USD ETH/USD"}
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/data/ostium_economics_universe}

OSTIUM_PAIRS="$PAIRS" OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
  exec "$ROOT/scripts/capture_ostium_economics_set.sh"
