#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
IMAGE=${OSTIUM_READONLY_IMAGE:-tradingagent-ostium-readonly:0.7.0-viem2.55.11}
DATA_DIR=${OSTIUM_QUOTE_DIR:-$ROOT/data/ostium_execution_quotes}
RAW="$DATA_DIR/spxusd_quotes.jsonl"
LOCAL_HM=$(TZ=America/New_York date +%H%M)

case "$LOCAL_HM" in
  09[3-5][0-9]|10[0-2][0-9]) WINDOW=open ;;
  12[0-5][0-9]) WINDOW=midday ;;
  15[0-5][0-9]) WINDOW=close ;;
  *) exit 0 ;;
esac

mkdir -p "$DATA_DIR"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build --tag "$IMAGE" "$ROOT/lab/ostium_readonly"
fi

docker run --rm --network bridge \
  --user "$(id -u):$(id -g)" \
  --entrypoint node \
  --mount "type=bind,src=$ROOT/academia/tools/collect_ostium_execution_quotes.mjs,dst=/app/collect_quotes.mjs,readonly" \
  --mount "type=bind,src=$DATA_DIR,dst=/quotes" \
  "$IMAGE" /app/collect_quotes.mjs \
  "--output=/quotes/spxusd_quotes.jsonl" --count=2 --interval-ms=2000 "--window=$WINDOW"

python3 "$ROOT/academia/tools/summarize_execution_quotes.py" "$RAW" \
  --output "$DATA_DIR/summary_latest.json"
