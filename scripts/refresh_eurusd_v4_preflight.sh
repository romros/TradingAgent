#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
STATE_DIR=${OSTIUM_EVIDENCE_DIR:-$ROOT/data/ostium_economics_universe}
SUMMARY="$STATE_DIR/eurusd_ostium_execution_summary_latest.json"
COSTS="$STATE_DIR/eurusd_costs_latest_v4.json"
PREFLIGHT="$STATE_DIR/eurusd_market_preflight_latest_v4.json"

test -f "$SUMMARY"
PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.ostium_small_account_cost_gate_v4 \
  --summary "$SUMMARY" --output "$COSTS" \
  --pair-id 2 --pair-from EUR --pair-to USD >/dev/null
PYTHONPATH="$ROOT" python3 -m lab.sq_bridge.eurusd_d1_market_preflight_v4 \
  --config "$ROOT/lab/sq_bridge/eurusd_d1_market_preflight_v4_config.json" \
  --output "$PREFLIGHT" >/dev/null

printf '%s\n%s\n' "$COSTS" "$PREFLIGHT"
