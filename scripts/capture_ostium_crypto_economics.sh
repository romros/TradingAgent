#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PAIRS=${OSTIUM_CRYPTO_PAIRS:-"BTC/USD ETH/USD"}
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/data/ostium_economics_universe}
STATUS=0

mkdir -p "$EVIDENCE_DIR"
for PAIR in $PAIRS; do
  PAIR_FROM=${PAIR%/*}
  SLUG=$(printf '%s' "${PAIR_FROM}USD" | tr '[:upper:]' '[:lower:]')
  BINANCE_SYMBOL="${PAIR_FROM}USDT"
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)
  BEFORE="$EVIDENCE_DIR/${SLUG}_binance_before_${STAMP}.json"
  AFTER="$EVIDENCE_DIR/${SLUG}_binance_after_${STAMP}.json"
  OBSERVATION="$EVIDENCE_DIR/${SLUG}_proxy_observation_${STAMP}.json"
  NATIVE="$EVIDENCE_DIR/${SLUG}_native_coverage_latest_v4.json"
  MAPPING="$EVIDENCE_DIR/${SLUG}_proxy_mapping_latest_v4.json"
  CANONICAL="$ROOT/lab/sq_bridge/evidence/${SLUG}_h4_canonical_source_v4.json"
  NATIVE_ROOT="/mnt/volume-SQ/dev/BrokerageService/datafiles/realtime_datalayer/candles/${PAIR_FROM}USD/America_New_York"

  if ! PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.capture_binance_book_ticker_v4 \
      --symbol "$BINANCE_SYMBOL" --output "$BEFORE" >/dev/null; then
    printf 'BINANCE_BEFORE_CAPTURE_FAILED pair=%s\n' "$PAIR" >&2
    STATUS=1
    continue
  fi
  if CAPTURE_OUTPUT=$(OSTIUM_PAIRS="$PAIR" OSTIUM_EVIDENCE_DIR="$EVIDENCE_DIR" \
      "$ROOT/scripts/capture_ostium_economics_set.sh"); then
    printf '%s\n' "$CAPTURE_OUTPUT"
  else
    printf 'OSTIUM_CAPTURE_FAILED pair=%s\n' "$PAIR" >&2
    STATUS=1
    continue
  fi
  NORMALIZED=$(printf '%s\n' "$CAPTURE_OUTPUT" | sed -n '2p')
  if ! PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.capture_binance_book_ticker_v4 \
      --symbol "$BINANCE_SYMBOL" --output "$AFTER" >/dev/null; then
    printf 'BINANCE_AFTER_CAPTURE_FAILED pair=%s\n' "$PAIR" >&2
    STATUS=1
    continue
  fi
  if ! PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.crypto_proxy_mapping_v4 observe \
      --before "$BEFORE" --ostium "$NORMALIZED" --after "$AFTER" \
      --output "$OBSERVATION" >/dev/null; then
    printf 'PROXY_OBSERVATION_FAILED pair=%s\n' "$PAIR" >&2
    STATUS=1
    continue
  fi
  if ! PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.ostium_native_coverage_gate \
      --root "$NATIVE_ROOT" --output "$NATIVE" >/dev/null; then
    printf 'NATIVE_COVERAGE_REFRESH_FAILED pair=%s\n' "$PAIR" >&2
    STATUS=1
    continue
  fi
  if [ ! -f "$CANONICAL" ]; then
    printf 'CANONICAL_H4_RECEIPT_MISSING pair=%s path=%s\n' "$PAIR" "$CANONICAL" >&2
    STATUS=1
    continue
  fi
  if ! PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.crypto_proxy_mapping_v4 gate \
      --observations "$EVIDENCE_DIR/${SLUG}_proxy_observation_*.json" \
      --native "$NATIVE" --canonical "$CANONICAL" --output "$MAPPING" >/dev/null; then
    printf 'PROXY_MAPPING_GATE_REFRESH_FAILED pair=%s\n' "$PAIR" >&2
    STATUS=1
  fi
done

exit "$STATUS"
