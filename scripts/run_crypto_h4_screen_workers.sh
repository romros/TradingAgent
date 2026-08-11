#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/data/ostium_economics_universe}
RUNTIME_DIR=${ALQUIMIA_CRYPTO_SCREEN_STATE_DIR:-/mnt/volume-SQ/user/alquimia_runtime/crypto_h4_screen_v4}
DESIGN="$ROOT/lab/sq_bridge/evidence/crypto_h4_experiment_design_v4.json"
SEMANTICS="$ROOT/lab/sq_bridge/crypto_h4_signal_semantics_v4.json"
MAX_CHUNKS=${ALQUIMIA_CRYPTO_SCREEN_MAX_CHUNKS:-1}
CHUNK_SIZE=${ALQUIMIA_CRYPTO_SCREEN_CHUNK_SIZE:-25}
STATUS=0

for SLUG in btcusd ethusd; do
  PREFLIGHT="$EVIDENCE_DIR/${SLUG}_h4_market_preflight_latest_v4.json"
  OUTPUT="$RUNTIME_DIR/$SLUG"
  if [ ! -f "$PREFLIGHT" ]; then
    printf 'CRYPTO_H4_PREFLIGHT_MISSING market=%s path=%s\n' "$SLUG" "$PREFLIGHT"
    continue
  fi
  if PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.crypto_h4_screen_worker_v4 \
      --preflight "$PREFLIGHT" --design "$DESIGN" --semantics "$SEMANTICS" \
      --output-dir "$OUTPUT" --max-chunks "$MAX_CHUNKS" \
      --chunk-size "$CHUNK_SIZE"; then
    :
  else
    printf 'CRYPTO_H4_SCREEN_WORKER_FAILED market=%s\n' "$SLUG" >&2
    STATUS=1
  fi
done

BTC_PREFLIGHT="$EVIDENCE_DIR/btcusd_h4_market_preflight_latest_v4.json"
ETH_PREFLIGHT="$EVIDENCE_DIR/ethusd_h4_market_preflight_latest_v4.json"
if [ -f "$BTC_PREFLIGHT" ] && [ -f "$ETH_PREFLIGHT" ]; then
  if PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.crypto_h4_screen_finalize_v4 \
      --btc-preflight "$BTC_PREFLIGHT" --eth-preflight "$ETH_PREFLIGHT" \
      --design "$DESIGN" --semantics "$SEMANTICS" \
      --runtime-root "$RUNTIME_DIR" --output "$RUNTIME_DIR/global_selector.json"; then
    :
  else
    printf 'CRYPTO_H4_SCREEN_FINALIZE_FAILED\n' >&2
    STATUS=1
  fi
fi

exit "$STATUS"
