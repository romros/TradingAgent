#!/usr/bin/env bash
# T8e: Executa test(s) dins Docker. Delegació a run.sh.
# Ús: ./test.sh [test_file]
#   sense args: ./scripts/run.sh component
#   amb test_file: pytest sobre el fitxer (dins Docker)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 1 ]; then
    exec "$ROOT/scripts/run.sh" component
fi

TEST_FILE="$1"
shift

# Executar pytest dins Docker
cd "$ROOT" && docker compose run --rm --no-deps \
    -v "$ROOT:/app" -e PYTHONPATH=/app \
    probe python -m pytest "$TEST_FILE" -v --tb=short "$@"
