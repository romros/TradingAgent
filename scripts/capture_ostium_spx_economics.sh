#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
IMAGE=${OSTIUM_READONLY_IMAGE:-tradingagent-ostium-readonly:0.7.0-viem2.55.11}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RAW="$ROOT/lab/sq_bridge/evidence/spxusd_ostium_execution_raw_${STAMP}.json"
NORMALIZED="$ROOT/lab/sq_bridge/evidence/spxusd_ostium_execution_normalized_${STAMP}.json"
SUMMARY="$ROOT/lab/sq_bridge/evidence/spxusd_ostium_execution_summary_latest.json"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build --tag "$IMAGE" "$ROOT/lab/ostium_readonly"
fi

docker run --rm --network bridge "$IMAGE" > "$RAW"
python3 "$ROOT/lab/sq_bridge/normalize_ostium_execution_snapshot.py" \
  "$RAW" --output "$NORMALIZED" >/dev/null
python3 "$ROOT/lab/sq_bridge/aggregate_ostium_execution_snapshots.py" \
  "$ROOT"/lab/sq_bridge/evidence/spxusd_ostium_execution_normalized_*.json \
  --output "$SUMMARY" >/dev/null

echo "$NORMALIZED"
echo "$SUMMARY"
