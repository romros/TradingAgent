#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 lab/sq_bridge/ibkr_sxr8_contract_probe.py \
  --output data/ibkr_sq_v2/turn_of_month/ibkr_sxr8_contract_probe.json
python3 lab/sq_bridge/sxr8_paper_readiness.py \
  --public-contract lab/sq_bridge/ibkr_sxr8_public_contract_v1.json \
  --account-probe data/ibkr_sq_v2/turn_of_month/ibkr_sxr8_contract_probe.json \
  --research data/ibkr_sq_v2/turn_of_month/cspx_transfer_v1.json \
  --calendar data/ibkr_sq_v2/turn_of_month/sxr8_calendar_plan_2012_2024.json \
  --output data/ibkr_sq_v2/turn_of_month/sxr8_paper_readiness.json
