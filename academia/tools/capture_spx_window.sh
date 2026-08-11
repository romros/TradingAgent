#!/usr/bin/env bash
# One-shot, read-only US500/USD quote capture. Raw output stays in /tmp.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 {open|midday|close} OUTPUT_STEM" >&2
  exit 2
fi

case "$1" in
  open|midday|close) window="$1" ;;
  *) echo "invalid session window: $1" >&2; exit 2 ;;
esac

stem="$2"
case "$stem" in
  /tmp/*) ;;
  *) echo "OUTPUT_STEM must be below /tmp" >&2; exit 2 ;;
esac

workspace=/mnt/volume-SQ/dev/TradingAgent
sdk_workdir=/tmp/ostium-sdk-inspect
raw="${stem}.jsonl"
summary="${stem}-summary.json"
log="${stem}.log"

exec >>"$log" 2>&1
echo "capture_start=$(date -u +%Y-%m-%dT%H:%M:%SZ) window=$window"

test -f "$sdk_workdir/package.json"
test -d "$sdk_workdir/node_modules/@ostium/builder-sdk"
test ! -e "$raw"

cd "$sdk_workdir"
node "$workspace/academia/tools/collect_ostium_execution_quotes.mjs" \
  "--output=$raw" "--window=$window" --count=20 --interval-ms=95000
python3 "$workspace/academia/tools/summarize_execution_quotes.py" \
  "$raw" --output "$summary"
sha256sum "$raw" "$summary"
echo "capture_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
