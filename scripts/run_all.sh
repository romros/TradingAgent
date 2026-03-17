#!/usr/bin/env bash
# T8e: Pipeline canònic de validació. TOT dins Docker.
# Ús: ./scripts/run_all.sh
#
# Ordre: component → integration → smoke → soak
# Cap prova compta com a validació operativa si s'executa al host.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  TradingAgent — Validació canònica (Docker-only)             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

EXIT=0

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

exit $EXIT
