"""
T8d-v: Test config d'assets canònic.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def test_probe_assets_config_canonical():
    """El símbol canònic NDXUSD queda reflectit al config runtime."""
    from packages.shared import config

    assert "NDXUSD" in config.ASSETS
    assert "QQQ" not in config.ASSETS
    assert "MSFT" in config.ASSETS
    assert "NVDA" in config.ASSETS
