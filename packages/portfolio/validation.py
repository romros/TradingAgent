"""
Validació paper vs backtest (T7b).
Càlcul de mètriques, probe_ok, classificació aligned/warning/diverged.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from packages.shared.baseline import (
    BASELINE_MSFT_D1,
    MARGIN_WR_PCT,
    MARGIN_EV_PCT,
    PROBE_OK_MAX_AGE_HOURS,
)

logger = logging.getLogger(__name__)


def compute_probe_ok(last_scan: Optional[dict]) -> bool:
    """
    probe_ok = TRUE si:
    - últim scan < 48h
    - cap asset amb status=error
    - sistema ha registrat almenys 1 scan
    """
    if last_scan is None:
        return False
    run_utc = last_scan.get("run_utc")
    if not run_utc:
        return False
    try:
        ts = datetime.fromisoformat(run_utc.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_h = (now - ts).total_seconds() / 3600
        if age_h >= PROBE_OK_MAX_AGE_HOURS:
            return False
    except (ValueError, TypeError):
        return False
    assets = last_scan.get("assets", {})
    for asset, info in assets.items():
        if isinstance(info, dict) and info.get("status") == "error":
            return False
    return True


def compute_winrate_robust(settled_count: int, wins: int) -> Tuple[Optional[float], str]:
    """
    Winrate robust: evita div/0 i pocs trades.
    Retorna (winrate_pct, confidence).
    confidence: "low" si settled < 3, "ok" altrament.
    """
    if settled_count < 3:
        return None, "low"
    if settled_count == 0:
        return None, "low"
    wr = round(100.0 * wins / settled_count, 1)
    return wr, "ok"


def compute_paper_metrics(trade_summary: dict) -> dict:
    """Mètriques paper agregades."""
    settled = trade_summary["settled_count"]
    wins = trade_summary["wins"]
    losses = trade_summary["losses"]
    pnl_total = trade_summary["pnl_total"]
    avg_pnl = trade_summary.get("avg_pnl_per_trade")

    winrate_pct, confidence = compute_winrate_robust(settled, wins)
    if avg_pnl is None and settled > 0:
        avg_pnl = round(pnl_total / settled, 2)

    return {
        "trades_total": settled,
        "wins": wins,
        "losses": losses,
        "winrate_pct": winrate_pct,
        "winrate_confidence": confidence,
        "pnl_total": pnl_total,
        "avg_pnl_per_trade": avg_pnl,
    }


def classify_validation(paper_metrics: dict) -> dict:
    """
    Compara paper vs baseline. Classificació: aligned | warning | diverged.
    Marges: WR ±10%, EV ±30%.
    """
    baseline = BASELINE_MSFT_D1
    paper_wr = paper_metrics.get("winrate_pct")
    paper_ev = paper_metrics.get("avg_pnl_per_trade")

    delta_wr = None
    delta_ev = None
    status = "aligned"

    if paper_wr is not None:
        delta_wr = round(paper_wr - baseline["winrate_pct"], 1)
        if abs(delta_wr) > MARGIN_WR_PCT:
            status = "diverged" if abs(delta_wr) > MARGIN_WR_PCT * 1.5 else "warning"

    if paper_ev is not None:
        delta_ev = round(paper_ev - baseline["avg_pnl_per_trade"], 2)
        ev_margin = baseline["avg_pnl_per_trade"] * (MARGIN_EV_PCT / 100)
        if abs(delta_ev) > ev_margin:
            if status == "aligned":
                status = "warning"
            if abs(delta_ev) > ev_margin * 1.5:
                status = "diverged"

    return {
        "status": status,
        "delta_wr_pct": delta_wr,
        "delta_ev": delta_ev,
        "baseline": baseline,
        "paper": {
            "winrate_pct": paper_wr,
            "avg_pnl_per_trade": paper_ev,
        },
    }


def run_validation(trade_summary: dict, last_scan: Optional[dict]) -> dict:
    """
    Executa validació completa: mètriques paper + comparació vs baseline.
    Emet log validation_completed.
    """
    paper_metrics = compute_paper_metrics(trade_summary)
    classification = classify_validation(paper_metrics)
    probe_ok = compute_probe_ok(last_scan)

    result = {
        "probe_ok": probe_ok,
        "paper_metrics": paper_metrics,
        "validation": classification,
    }

    logger.info(
        "validation_completed trades=%s winrate=%s ev=%s status=%s",
        paper_metrics["trades_total"],
        paper_metrics["winrate_pct"],
        paper_metrics["avg_pnl_per_trade"],
        classification["status"],
    )
    return result
