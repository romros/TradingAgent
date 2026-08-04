from __future__ import annotations

import os

from packages.market.ostium_clean_d1 import OstiumCleanD1Feed
from packages.runtime.close_hold_probe import CloseHoldPaperProbe, CloseHoldProbeConfig
from packages.strategy.msft_close_drift import MsftCloseDriftStrategy


def run_msft_close_drift_probe() -> dict:
    # v24 calcula el senyal i l'entrada amb el close regular de les 16:00 ET.
    # Ostium força el tancament de les posicions intradia a les 15:45 ET; per
    # tant aquest fill no existeix. Bloquegem també les invocacions manuals,
    # no només el scheduler, fins que una versió pre-close sigui revalidada.
    if os.getenv("MSFT_DRIFT_EXECUTION_COMPATIBLE", "false").lower() not in (
        "1", "true", "yes"
    ):
        return {
            "status": "BLOCKED_EXECUTION_WINDOW",
            "strategy": MsftCloseDriftStrategy.STRATEGY_NAME,
            "reason": "signal_requires_16_00_et_close_after_ostium_15_45_et_cutoff",
            "opened": None,
            "settled": None,
        }
    strategy = MsftCloseDriftStrategy()
    feed = OstiumCleanD1Feed(os.getenv("BS_BASE_URL", "http://localhost:8081"))
    config = CloseHoldProbeConfig(
        db_path=os.getenv("MSFT_DRIFT_DB_PATH", "data/msft_close_drift_probe.db"),
        capital_initial=float(os.getenv("MSFT_DRIFT_CAPITAL", "200")),
        leverage=int(os.getenv("MSFT_DRIFT_LEVERAGE", "4")),
        risk_per_trade_pct=float(os.getenv("MSFT_DRIFT_RISK_PCT", "0.01")),
        fee_roundtrip_bps=float(os.getenv("MSFT_DRIFT_COST_BPS", "36")),
    )
    return CloseHoldPaperProbe(strategy, config).run(feed.fetch("MSFT"))
