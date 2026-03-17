#!/usr/bin/env bash
# T8e: Wrapper canònic de proves. Executa DINS Docker.
# Ús: ./scripts/run.sh <component|integration|smoke|soak>
#
# component: scripts Python purs testing/unit (0-network)
# integration: scripts Python purs (API/DB dins contenidor)
# smoke: servei arrencat, /health, /quick-status, POST /scan, snapshot
# soak: servei viu N minuts, sense crash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

MODE="${1:-}"
if [ -z "$MODE" ]; then
    echo "Ús: $0 <component|integration|smoke|soak>"
    exit 1
fi

PROBE_URL="${PROBE_URL:-http://localhost:8090}"
SOAK_MINUTES="${SOAK_MINUTES:-2}"

run_component() {
    echo "═══════════════════════════════════════════"
    echo "  Component (unit tests, dins Docker)"
    echo "═══════════════════════════════════════════"
    docker compose run --rm --no-deps \
        -v "$ROOT:/app" -e PYTHONPATH=/app \
        probe python testing/run_all.py 2>&1
}

run_integration() {
    echo "═══════════════════════════════════════════"
    echo "  Integration (dins Docker)"
    echo "═══════════════════════════════════════════"
    if [ -d "$ROOT/testing/integration" ] && [ -n "$(ls "$ROOT/testing/integration"/test_*.py 2>/dev/null)" ]; then
        docker compose run --rm --no-deps \
            -v "$ROOT:/app" -e PYTHONPATH=/app \
            probe python testing/run_integration.py 2>&1
    else
        echo "  (no integration tests; skipping)"
    fi
}

run_smoke() {
    echo "═══════════════════════════════════════════"
    echo "  Smoke (servei real dins Docker)"
    echo "═══════════════════════════════════════════"
    mkdir -p "$ROOT/data" "$ROOT/data/probe_snapshots"
    ARTIFACTS_DIR="${ARTIFACTS_DIR:-$ROOT/data/smoke_artifacts}"
    mkdir -p "$ARTIFACTS_DIR"
    TS=$(date +%Y%m%d_%H%M%S)

    echo "  Build + up..."
    docker compose build probe 2>/dev/null || true
    docker compose up -d probe

    echo "  Waiting for /health..."
    for i in $(seq 1 30); do
        if curl -sf "$PROBE_URL/health" >/dev/null 2>&1; then
            echo "  ✓ Probe ready"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "  ✗ Probe not ready after 30s"
            docker compose logs probe 2>&1 | tail -80
            exit 6
        fi
        sleep 1
    done

    echo "  /health..."
    curl -sf "$PROBE_URL/health" | tee "$ARTIFACTS_DIR/${TS}_health.json" || { echo "  ✗ /health failed"; exit 7; }
    cp "$ARTIFACTS_DIR/${TS}_health.json" "$ARTIFACTS_DIR/health.json" 2>/dev/null || true
    echo ""

    echo "  /quick-status..."
    curl -sf "$PROBE_URL/quick-status" | tee "$ARTIFACTS_DIR/${TS}_quick_status.json" || { echo "  ✗ /quick-status failed"; exit 8; }
    cp "$ARTIFACTS_DIR/${TS}_quick_status.json" "$ARTIFACTS_DIR/quick_status.json" 2>/dev/null || true
    echo ""

    echo "  POST /scan..."
    curl -sf -X POST "$PROBE_URL/scan" | tee "$ARTIFACTS_DIR/${TS}_scan.json" || { echo "  ✗ POST /scan failed"; exit 9; }
    echo ""

    echo "  Snapshot..."
    sleep 2
    SNAPSHOTS=$(ls -1 "$ROOT/data/probe_snapshots/"*.md 2>/dev/null | tail -1)
    if [ -n "$SNAPSHOTS" ]; then
        echo "  ✓ Snapshot: $SNAPSHOTS"
        cp "$SNAPSHOTS" "$ARTIFACTS_DIR/${TS}_snapshot.md" 2>/dev/null || true
        cp "$SNAPSHOTS" "$ARTIFACTS_DIR/latest_snapshot.md" 2>/dev/null || true
    else
        echo "  ⚠ No snapshot found (check data/probe_snapshots/)"
    fi

    echo "  docker compose ps..."
    docker compose ps | tee "$ARTIFACTS_DIR/${TS}_ps.txt"

    cp "$ARTIFACTS_DIR/${TS}_ps.txt" "$ARTIFACTS_DIR/docker_ps.txt" 2>/dev/null || true

    echo ""
    echo "  ✓ Smoke OK"
    echo "  Artifacts: $ARTIFACTS_DIR"
}

run_soak() {
    echo "═══════════════════════════════════════════"
    echo "  Soak (${SOAK_MINUTES} min, servei viu)"
    echo "═══════════════════════════════════════════"
    mkdir -p "$ROOT/data"
    ARTIFACTS_DIR="${ARTIFACTS_DIR:-$ROOT/data/soak_artifacts}"
    mkdir -p "$ARTIFACTS_DIR"
    TS=$(date +%Y%m%d_%H%M%S)
    LOG="$ARTIFACTS_DIR/${TS}_soak.log"

    echo "  Build + up..."
    docker compose build probe 2>/dev/null || true
    docker compose up -d probe

    echo "  Waiting for /health..."
    for i in $(seq 1 30); do
        if curl -sf "$PROBE_URL/health" >/dev/null 2>&1; then
            echo "  ✓ Probe ready"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "  ✗ Probe not ready"
            exit 6
        fi
        sleep 1
    done

    echo "  Soak ${SOAK_MINUTES} min..."
    END=$((SECONDS + SOAK_MINUTES * 60))
    FAILED=0
    while [ $SECONDS -lt $END ]; do
        if ! curl -sf "$PROBE_URL/health" >/dev/null 2>&1; then
            echo "  ✗ /health failed at $SECONDS s"
            FAILED=1
            break
        fi
        sleep 30
        echo "  ... ${SECONDS}s elapsed"
    done

    docker compose logs probe 2>&1 | tail -100 > "$LOG"
    cp "$LOG" "$ARTIFACTS_DIR/soak.log" 2>/dev/null || true
    echo "  Logs: $LOG"

    if [ "$FAILED" -eq 1 ]; then
        echo "  ✗ Soak FAILED"
        exit 10
    fi
    echo "  ✓ Soak OK"
}

case "$MODE" in
    component)   run_component ;;
    integration) run_integration ;;
    smoke)       run_smoke ;;
    soak)        run_soak ;;
    *)
        echo "Mode desconegut: $MODE (component|integration|smoke|soak)"
        exit 1
        ;;
esac
