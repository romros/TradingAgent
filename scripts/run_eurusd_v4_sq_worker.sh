#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SCREEN_DIR=${ALQUIMIA_EURUSD_SCREEN_DIR:-$ROOT/data/alquimia_v4/eurusd-d1-alquimia-v4/screen-bootstrap}
WORKER_DIR=${ALQUIMIA_EURUSD_SQ_WORKER_DIR:-$ROOT/data/alquimia_v4/eurusd-d1-alquimia-v4/sq-worker}
TEMPORAL_DIR=${ALQUIMIA_EURUSD_TEMPORAL_WORKER_DIR:-$ROOT/data/alquimia_v4/eurusd-d1-alquimia-v4/temporal-worker}
ROBUSTNESS_DIR=${ALQUIMIA_EURUSD_ROBUSTNESS_WORKER_DIR:-$ROOT/data/alquimia_v4/eurusd-d1-alquimia-v4/robustness-worker}
SMALL_ACCOUNT_DIR=${ALQUIMIA_EURUSD_SMALL_ACCOUNT_WORKER_DIR:-$ROOT/data/alquimia_v4/eurusd-d1-alquimia-v4/small-account-worker}
HOLDOUT_DIR=${ALQUIMIA_EURUSD_HOLDOUT_WORKER_DIR:-$ROOT/data/alquimia_v4/eurusd-d1-alquimia-v4/holdout-worker}
CONFIG=${ALQUIMIA_EURUSD_SQ_WORKER_CONFIG:-$ROOT/lab/sq_bridge/eurusd_v4_sq_worker_config.json}

PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.eurusd_v4_sq_worker \
  --screen-dir "$SCREEN_DIR" --config "$CONFIG" --output-dir "$WORKER_DIR"

PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.eurusd_v4_temporal_worker \
  --screen-dir "$SCREEN_DIR" --sq-worker-dir "$WORKER_DIR" \
  --worker-config "$CONFIG" --output-dir "$TEMPORAL_DIR"

PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.eurusd_v4_robustness_worker \
  --temporal-worker-dir "$TEMPORAL_DIR" --worker-config "$CONFIG" \
  --output-dir "$ROBUSTNESS_DIR"

PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.eurusd_v4_small_account_worker \
  --robustness-worker-dir "$ROBUSTNESS_DIR" --worker-config "$CONFIG" \
  --output-dir "$SMALL_ACCOUNT_DIR"

PYTHONPATH="$ROOT" exec python3 -m lab.sq_bridge.eurusd_v4_holdout_worker \
  --small-account-worker-dir "$SMALL_ACCOUNT_DIR" --worker-config "$CONFIG" \
  --output-dir "$HOLDOUT_DIR"
