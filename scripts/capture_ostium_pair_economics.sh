#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
IMAGE=${OSTIUM_READONLY_IMAGE:-tradingagent-ostium-readonly:0.7.0-generic}
PAIR=${OSTIUM_PAIR:?Set OSTIUM_PAIR, for example USD/JPY}
PAIR_FROM=${PAIR%/*}
PAIR_TO=${PAIR#*/}
SLUG=$(printf '%s' "$PAIR_FROM$PAIR_TO" | tr '[:upper:]' '[:lower:]')
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/lab/sq_bridge/evidence}
RAW="$EVIDENCE_DIR/${SLUG}_ostium_execution_raw_${STAMP}.json"
NORMALIZED="$EVIDENCE_DIR/${SLUG}_ostium_execution_normalized_${STAMP}.json"
SUMMARY="$EVIDENCE_DIR/${SLUG}_ostium_execution_summary_latest.json"

mkdir -p "$EVIDENCE_DIR"
docker image inspect "$IMAGE" >/dev/null
docker run --rm --network bridge --env "OSTIUM_PAIR=$PAIR" \
  --env "OSTIUM_NOTIONALS=${OSTIUM_NOTIONALS:-10,20,50,100,200,500,1000}" \
  "$IMAGE" > "$RAW"
python3 "$ROOT/lab/sq_bridge/normalize_ostium_execution_snapshot.py" \
  "$RAW" --output "$NORMALIZED" --pair-from "$PAIR_FROM" --pair-to "$PAIR_TO" >/dev/null
PAIR_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["instrument"]["pair_id"])' "$NORMALIZED")
python3 "$ROOT/lab/sq_bridge/aggregate_ostium_execution_snapshots.py" \
  "$EVIDENCE_DIR"/${SLUG}_ostium_execution_normalized_*.json \
  --pair-id "$PAIR_ID" --output "$SUMMARY" >/dev/null

printf '%s\n%s\n%s\n' "$RAW" "$NORMALIZED" "$SUMMARY"
