#!/usr/bin/env bash
# Usage: ./test.sh <test_file>
# Runs a single test file inside a Python container.
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <test_file>"
    echo "Example: $0 testing/unit/test_indicators.py"
    exit 1
fi

TEST_FILE="$1"
shift

docker run --rm \
    -v "$(pwd):/app" \
    -w /app \
    -e PYTHONPATH=/app \
    python:3.11-slim \
    python "$TEST_FILE" "$@"
