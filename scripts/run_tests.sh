#!/usr/bin/env bash
# T8e: Suite de tests. Delegació a run.sh component (Docker-only).
# Ús: ./scripts/run_tests.sh [unit|integration|all]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SUITE="${1:-unit}"
case "$SUITE" in
    unit)        exec "$SCRIPT_DIR/run.sh" component ;;
    integration) exec "$SCRIPT_DIR/run.sh" integration ;;
    all)         exec "$SCRIPT_DIR/run_all.sh" ;;
    *)
        echo "Ús: $0 <unit|integration|all>"
        exit 1
        ;;
esac
