#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SCREEN_DIR=${ALQUIMIA_US500_SCREEN_DIR:-$ROOT/data/alquimia_v4/us500-d1-alquimia-v4/screen-bootstrap}
WORKER_DIR=${ALQUIMIA_US500_SQ_WORKER_DIR:-$ROOT/data/alquimia_v4/us500-d1-alquimia-v4/sq-worker}
CONFIG=${ALQUIMIA_US500_SQ_WORKER_CONFIG:-$ROOT/lab/sq_bridge/us500_v4_sq_worker_config.json}

PYTHONPATH="$ROOT" exec python3 -m lab.sq_bridge.us500_v4_sq_worker \
  --screen-dir "$SCREEN_DIR" --config "$CONFIG" --output-dir "$WORKER_DIR"
