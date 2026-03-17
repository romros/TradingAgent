#!/usr/bin/env bash
# T8e/T8e-v: Pipeline canònic de validació. TOT dins Docker.
# Ús: ./scripts/run_all.sh
#
# Ordre: component → integration → smoke → soak
# Artifacts a docs/validation/ (versionats, consultables per raw URL).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

ARTIFACTS_DIR="${ARTIFACTS_DIR:-$ROOT/docs/validation}"
mkdir -p "$ARTIFACTS_DIR"
export ARTIFACTS_DIR

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  TradingAgent — Validació canònica (Docker-only)             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

EXIT=0

{
echo "▶ 1/4 Component"
"$SCRIPT_DIR/run.sh" component || EXIT=1
echo ""

echo "▶ 2/4 Integration"
"$SCRIPT_DIR/run.sh" integration || EXIT=1
echo ""

echo "▶ 3/4 Smoke"
"$SCRIPT_DIR/run.sh" smoke || EXIT=1
echo ""

echo "▶ 4/4 Soak"
"$SCRIPT_DIR/run.sh" soak || EXIT=1
echo ""

# Aturar servei després de soak
docker compose down 2>/dev/null || true

echo ""
if [ "$EXIT" -eq 0 ]; then
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  ✓ Validació completa OK                                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
else
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  ✗ Validació FALLIDA                                         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
fi
echo ""
echo "$EXIT" > "$ARTIFACTS_DIR/.exit"
} 2>&1 | tee "$ARTIFACTS_DIR/run_all.log"

EXIT=$(cat "$ARTIFACTS_DIR/.exit" 2>/dev/null || echo 0)
exit "$EXIT"
