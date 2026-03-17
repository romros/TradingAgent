#!/usr/bin/env bash
# T8e: Executa test(s) dins Docker. Scripts Python purs (NO pytest).
# Ús: ./test.sh [test_file]
#   sense args: ./scripts/run.sh component
#   amb test_file: python test_file directament (dins Docker)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 1 ]; then
    exec "$ROOT/scripts/run.sh" component
fi

TEST_FILE="$1"
shift

cd "$ROOT" && docker compose run --rm --no-deps \
    -v "$ROOT:/app" -e PYTHONPATH=/app \
    probe python "$TEST_FILE" "$@"
