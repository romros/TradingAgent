"""
T7d: Tests 0-network per daily_snapshot.
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from packages.runtime.daily_snapshot import (
    build_daily_snapshot,
    render_snapshot_md,
    SNAPSHOTS_DIR_DEFAULT,
)


def test_snapshot_filename_deterministic():
    """Nom i ruta del fitxer són deterministes (YYYY-MM-DD.md)."""
    with tempfile.TemporaryDirectory() as tmp:
        result = build_daily_snapshot(
            db_path=":memory:",
            output_dir=tmp,
            assets=[],
            trade_summary_override={"open_count": 0, "settled_count": 0, "wins": 0, "losses": 0, "pnl_total": 0.0},
            last_scan_override={"run_utc": "2026-03-17T12:00:00Z", "status": "ok"},
            validation_result_override={"classification": "aligned"},
            data_quality_override={"source": "yfinance", "assets": {}},
            proxy_result_override={"classification": "aligned"},
            bs_audit_override={"source": "brokerage_service", "assets": []},
            live_readiness_override={"status": "LIVE_NOT_READY"},
        )
        path = Path(result["path"])
        assert path.suffix == ".md"
        # Nom YYYY-MM-DD
        stem = path.stem
        parts = stem.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4 and parts[0].isdigit()
        assert len(parts[1]) == 2 and parts[1].isdigit()
        assert len(parts[2]) == 2 and parts[2].isdigit()
        assert path.parent == Path(tmp)


def test_snapshot_render_contains_core_sections():
    """El snapshot inclou validation, live-readiness, data-quality i trade_summary."""
    sections = {
        "trade_summary": {"status": "ok", "data": {"open_count": 0, "settled_count": 1, "wins": 1, "losses": 0, "pnl_total": 10.0}},
        "last_scan": {"status": "ok", "data": {"run_utc": "2026-03-17T12:00:00Z", "status": "ok"}},
        "validation": {"status": "ok", "data": {"classification": "aligned"}},
        "data_quality": {"status": "ok", "data": {"source": "yfinance", "assets": {"MSFT": {"status": "ok", "candles_count": 252}}}},
        "proxy_validation": {"status": "ok", "data": {"classification": "aligned"}},
        "bs_audit": {"status": "ok", "data": {"source": "brokerage_service"}},
        "live_readiness": {"status": "ok", "data": {"status": "LIVE_READY"}},
    }
    md = render_snapshot_md(sections)
    assert "### validation" in md
    assert "### live_readiness" in md
    assert "### data_quality" in md
    assert "### trade_summary" in md
    assert "aligned" in md
    assert "LIVE_READY" in md


def test_snapshot_write_no_crash_on_partial_error():
    """Si una secció falla, el snapshot no trenca; degrada amb secció error."""
    with tempfile.TemporaryDirectory() as tmp:
        # DB buida / inexistent pot donar error a trade_summary o last_scan
        # Passem overrides per evitar xarxa i DB
        result = build_daily_snapshot(
            db_path="/nonexistent/path/foo.db",
            output_dir=tmp,
            assets=["MSFT"],
            trade_summary_override={"open_count": 0, "settled_count": 0, "wins": 0, "losses": 0, "pnl_total": 0.0},
            last_scan_override={"run_utc": "2026-03-17T12:00:00Z", "status": "ok"},
            validation_result_override={"classification": "aligned"},
            data_quality_override={"source": "yfinance", "assets": {"MSFT": {"status": "ok", "candles_count": 252}}},
            proxy_result_override={"classification": "aligned"},
            bs_audit_override={"source": "brokerage_service", "assets": []},
            live_readiness_override={"status": "LIVE_NOT_READY"},
        )
        assert "path" in result
        assert result["status"] in ("ok", "warning")
        assert Path(result["path"]).exists()
        content = Path(result["path"]).read_text()
        assert "validation" in content
        assert "live_readiness" in content


def test_snapshot_uses_existing_canonical_results():
    """El snapshot no recalcula; usa resultats canònics passats per override."""
    with tempfile.TemporaryDirectory() as tmp:
        canonical_val = {"classification": "diverged", "paper_winrate": 0.6, "backtest_winrate": 0.5}
        canonical_lr = {"status": "LIVE_SHADOW_READY", "checks": {}}
        result = build_daily_snapshot(
            db_path=":memory:",
            output_dir=tmp,
            assets=[],
            trade_summary_override={"open_count": 0, "settled_count": 2, "wins": 1, "losses": 1, "pnl_total": -5.0},
            last_scan_override={"run_utc": "2026-03-17T12:00:00Z", "status": "ok"},
            validation_result_override=canonical_val,
            data_quality_override={"source": "yfinance", "assets": {}},
            proxy_result_override={"classification": "warning"},
            bs_audit_override={"source": "brokerage_service", "assets": []},
            live_readiness_override=canonical_lr,
        )
        content = Path(result["path"]).read_text()
        assert "diverged" in content
        assert "LIVE_SHADOW_READY" in content
        assert "0.6" in content
        assert "0.5" in content


def _run_tests():
    ok = True
    tests = [
        test_snapshot_filename_deterministic,
        test_snapshot_render_contains_core_sections,
        test_snapshot_write_no_crash_on_partial_error,
        test_snapshot_uses_existing_canonical_results,
    ]
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except Exception as e:
            import traceback
            print(f"  FAIL {t.__name__}: {e}")
            traceback.print_exc()
            ok = False
    return ok


if __name__ == "__main__":
    print("=== Daily Snapshot Unit Tests ===")
    sys.exit(0 if _run_tests() else 1)
