#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
IMAGE=${OSTIUM_READONLY_IMAGE:-tradingagent-ostium-readonly:0.7.0-viem2.55.11}
DATA_DIR=${OSTIUM_QUOTE_DIR:-$ROOT/data/ostium_execution_quotes}
RAW="$DATA_DIR/spxusd_quotes.jsonl"
SUMMARY="$DATA_DIR/summary_latest.json"
COSTS="$DATA_DIR/costs_latest.json"
PREFLIGHT="$DATA_DIR/market_preflight_latest.json"
PREFLIGHT_CONFIG="$ROOT/lab/sq_bridge/us500_d1_market_preflight_v4_config.json"
CANONICAL_SOURCE="$ROOT/lab/sq_bridge/evidence/us500_d1_canonical_v4.csv"
SCREEN_DIR=${ALQUIMIA_US500_SCREEN_DIR:-$ROOT/data/alquimia_v4/us500-d1-alquimia-v4/screen-bootstrap}
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
  --output "$SUMMARY"
python3 "$ROOT/lab/sq_bridge/spxusd_small_account_cost_gate.py" \
  --summary "$SUMMARY" --output "$COSTS"
python3 "$ROOT/lab/sq_bridge/us500_d1_market_preflight_v4.py" \
  --config "$PREFLIGHT_CONFIG" --output "$PREFLIGHT"

# WAITING does not create screen state. The first mature PASS freezes every
# mutable input and evaluates train exactly once; SQCLI remains inert.
PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.us500_v4_screen_trigger \
  --preflight "$PREFLIGHT" --source "$CANONICAL_SOURCE" \
  --output-dir "$SCREEN_DIR"
