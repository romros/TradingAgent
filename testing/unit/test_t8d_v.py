"""
T8d-v: Test config d'assets canònic.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def test_probe_assets_config_defaults_to_certified_economics():
    """NDXUSD conserva mapping però no opera per defecte fins superar el gate."""
    from packages.shared import config

    assert config.ASSETS == ["MSFT", "NVDA"]
    assert config.LEVERAGE_BY_ASSET["NDXUSD"] == 5
    assert "MSFT" in config.ASSETS
    assert "NVDA" in config.ASSETS


def _run_tests():
    ok = True
    tests = [test_probe_assets_config_canonical]
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
    print("=== T8d-v Unit Tests ===")
    sys.exit(0 if _run_tests() else 1)
