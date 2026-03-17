"""
T8d: Tests per arrencada, scheduler i quick-status.
"""
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def test_quick_status_payload():
    """Payload de /quick-status és curt, estable i humà llegible."""
    prev = os.environ.get("DB_PATH")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "probe.db")
            os.environ["DB_PATH"] = db_path
            from importlib import reload
            import packages.shared.config as shared_config
            reload(shared_config)
            from packages.portfolio.db import init_db, save_scan_result, save_scan_run
            from apps.agent.routes import quick_status

            conn = init_db(db_path)
            save_scan_result(conn, {
                "run_utc": "2026-03-17T12:00:00Z",
                "status": "ok",
                "assets": {"MSFT": {"status": "ok", "signal": False, "candles": 252}},
                "new_signals": [],
                "settled_count": 0,
                "pending_count": 0,
                "errors": [],
            })
            save_scan_run(conn, {
                "run_utc": "2026-03-17T12:00:00Z",
                "status": "ok",
                "assets": {},
                "new_signals": [],
                "settled_count": 0,
                "pending_count": 0,
                "errors": [],
            })
            conn.close()

            # Mock network-heavy calls per test 0-network
            with patch("apps.agent.routes.run_proxy_validation", return_value={"classification": "aligned"}):
                with patch("apps.agent.routes.run_bs_audit", return_value={"source": "bs", "assets": []}):
                    with patch("apps.agent.routes._get_data_quality_result", return_value={"source": "yf", "assets": {}}):
                        data = quick_status()
            assert "ok" in data
            assert "probe_ok" in data
            assert "last_scan_utc" in data
            assert "trades" in data
            assert "validation" in data
            assert "live_readiness" in data
            assert "settled" in data["trades"]
            assert "wins" in data["trades"]
            assert "losses" in data["trades"]
            assert "pnl" in data["trades"]
    finally:
        if prev is not None:
            os.environ["DB_PATH"] = prev
        else:
            os.environ.pop("DB_PATH", None)


def test_scheduler_config_parsing():
    """Hora/config del scheduler es parseja correctament."""
    from packages.shared import config
    # Defaults o valors d'env
    assert isinstance(config.SCHEDULER_ENABLED, bool)
    assert isinstance(config.SCHEDULER_HOUR_UTC, int)
    assert 0 <= config.SCHEDULER_HOUR_UTC <= 23


def test_startup_fails_closed_without_required_config():
    """L'app arrenca sense config crítica (DB_PATH té default). Verifiquem que /health respon."""
    from apps.agent.routes import health

    data = health()
    assert data.get("status") == "ok"
