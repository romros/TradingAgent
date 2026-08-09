#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
IMAGE=${OSTIUM_READONLY_IMAGE:-tradingagent-ostium-readonly:0.7.0-viem2.55.11}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/lab/sq_bridge/evidence}
RAW="$EVIDENCE_DIR/spxusd_ostium_execution_raw_${STAMP}.json"
NORMALIZED="$EVIDENCE_DIR/spxusd_ostium_execution_normalized_${STAMP}.json"
SUMMARY="$EVIDENCE_DIR/spxusd_ostium_execution_summary_latest.json"

mkdir -p "$EVIDENCE_DIR"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build --tag "$IMAGE" "$ROOT/lab/ostium_readonly"
fi

docker run --rm --network bridge "$IMAGE" > "$RAW"
python3 "$ROOT/lab/sq_bridge/normalize_ostium_execution_snapshot.py" \
  "$RAW" --output "$NORMALIZED" >/dev/null
python3 "$ROOT/lab/sq_bridge/aggregate_ostium_execution_snapshots.py" \
  "$EVIDENCE_DIR"/spxusd_ostium_execution_normalized_*.json \
  --output "$SUMMARY" >/dev/null

echo "$NORMALIZED"
echo "$SUMMARY"
