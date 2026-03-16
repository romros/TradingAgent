#!/usr/bin/env bash
# Run all test suites.
# Usage: ./scripts/run_tests.sh [suite]
#   suite: "unit" | "integration" | "all" (default: "unit")
set -euo pipefail

SUITE="${1:-unit}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

run_suite() {
    local suite_dir="$1"
    local suite_name="$2"
    local failed=0
    local total=0
    local passed=0

    echo "═══════════════════════════════════════════"
    echo "  Suite: $suite_name"
    echo "═══════════════════════════════════════════"

    for f in "$suite_dir"/test_*.py; do
        [ -f "$f" ] || continue
        total=$((total + 1))
        echo -n "  $(basename "$f")... "
        if "$ROOT/test.sh" "$f" 2>&1 | tail -1; then
            passed=$((passed + 1))
        else
            failed=$((failed + 1))
            echo "FAIL"
        fi
    done

    echo "───────────────────────────────────────────"
    echo "  $suite_name: $passed/$total passed"
    [ "$failed" -eq 0 ] || echo "  ⚠ $failed FAILED"
    echo ""
    return "$failed"
}

EXIT=0

if [ "$SUITE" = "unit" ] || [ "$SUITE" = "all" ]; then
    run_suite "$ROOT/testing/unit" "Unit" || EXIT=1
fi

if [ "$SUITE" = "integration" ] || [ "$SUITE" = "all" ]; then
    run_suite "$ROOT/testing/integration" "Integration" || EXIT=1
fi

exit $EXIT
