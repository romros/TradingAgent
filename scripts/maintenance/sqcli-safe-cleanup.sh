#!/usr/bin/env bash
# Conservative SQCLI cleanup. Dry-run unless --execute is explicitly supplied.
set -euo pipefail

container="sqcli-docker"
mode="${1:---dry-run}"
if [[ "$mode" != "--dry-run" && "$mode" != "--execute" ]]; then
  echo "usage: $0 [--dry-run|--execute]" >&2
  exit 2
fi

docker inspect "$container" >/dev/null
running="$(docker inspect -f '{{.State.Running}}' "$container")"
if [[ "$running" != "true" ]]; then
  echo "BLOCK: $container is not running; cannot prove project state" >&2
  exit 1
fi

# SQ's own task logs are authoritative: a recently running task blocks cleanup.
if docker exec "$container" bash -c \
  'find /home/squser/SQ/user/projects -path "*/log/global_log_*.log" -mmin -2 -type f -exec grep -l "TASK STARTED" {} + 2>/dev/null' \
  | grep -q .; then
  echo "BLOCK: recent SQ project activity detected" >&2
  exit 1
fi

docker exec "$container" bash -c '
  set -eu
  path=/home/squser/SQ/internal/tmp/stock
  bytes=$(du -sb "$path" 2>/dev/null | cut -f1 || echo 0)
  jars=$(find "$path" -type f -name "*.jar" 2>/dev/null | wc -l)
  printf "tmp_stock_bytes=%s\ntemporary_jars=%s\n" "$bytes" "$jars"
'

if [[ "$mode" == "--dry-run" ]]; then
  echo "DRY_RUN: nothing deleted"
  exit 0
fi

docker exec "$container" bash -c '
  set -eu
  path=/home/squser/SQ/internal/tmp/stock
  find "$path" -type f -name "*.jar" -delete
  find "$path" -type d -empty -delete 2>/dev/null || true
'
echo "PASS: deleted only regenerable internal/tmp/stock JAR files"
