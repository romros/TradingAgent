import json
from pathlib import Path

from lab.sq_bridge.ostium_small_account_cost_gate_v4 import REQUIRED_NOTIONALS_USDC


def test_default_capture_covers_full_200_usdc_margin_ceiling():
    script = (Path(__file__).parents[2] / "scripts" /
              "capture_ostium_pair_economics.sh").read_text()
    expected = ",".join(str(value) for value in REQUIRED_NOTIONALS_USDC)
    assert f"OSTIUM_NOTIONALS:-{expected}" in script


def test_raw_snapshot_is_published_atomically_only_after_docker_succeeds():
    script = (Path(__file__).parents[2] / "scripts" /
              "capture_ostium_pair_economics.sh").read_text()
    assert 'RAW_PENDING="${RAW}.pending.$$"' in script
    assert 'NORMALIZED_PENDING="${NORMALIZED}.pending.$$"' in script
    assert 'trap \'rm -f "$RAW_PENDING" "$NORMALIZED_PENDING"\'' in script
    assert '"$IMAGE" > "$RAW_PENDING"' in script
    assert '"$RAW_PENDING" --output "$NORMALIZED_PENDING"' in script
    assert 'mv "$RAW_PENDING" "$RAW"' in script
    assert 'mv "$NORMALIZED_PENDING" "$NORMALIZED"' in script


def test_capture_reports_the_installed_sdk_and_verifies_lock_integrity():
    root = Path(__file__).parents[2]
    capture = (root / "lab" / "ostium_readonly" / "capture_spx.mjs").read_text()
    lock = json.loads((root / "lab" / "ostium_readonly" / "package-lock.json").read_text())
    sdk = lock["packages"]["node_modules/@ostium/builder-sdk"]
    assert sdk["version"] == "0.7.0"
    assert sdk["integrity"].startswith("sha512-")
    assert "sdkPackage.version !== lockedSdk.version" in capture
    assert "lockedSdk.integrity.startsWith('sha512-')" in capture
    assert "version: sdkPackage.version" in capture
    assert "version: '0.7.0'" not in capture


def test_universe_capture_prioritizes_eurusd_and_is_failure_isolated():
    script = (Path(__file__).parents[2] / "scripts" /
              "capture_ostium_research_universe_economics.sh").read_text()
    assert 'PAIRS=${OSTIUM_RESEARCH_PAIRS:-"EUR/USD ' in script
    assert 'capture_ostium_economics_set.sh' in script
    assert 'PREFLIGHT_REFRESH_FAILED pair=EUR/USD' in script
    assert 'eurusd_v4_screen_trigger' in script
    assert 'EURUSD_SCREEN_TRIGGER_FAILED' in script
    assert 'ALQUIMIA_EURUSD_SCREEN_DIR' in script
    assert 'exit "$STATUS"' in script


def test_generic_set_refreshes_each_pair_independently():
    root = Path(__file__).parents[2]
    script = (root / "scripts/capture_ostium_economics_set.sh").read_text()
    assert 'PAIRS=${OSTIUM_PAIRS:?' in script
    assert 'for PAIR in $PAIRS' in script
    assert 'capture_ostium_pair_economics.sh' in script
    assert 'ostium_small_account_cost_gate_v4' in script
    assert 'CAPTURE_FAILED pair=%s' in script
    assert 'exit "$STATUS"' in script


def test_crypto_capture_is_hourly_every_day_and_separately_locked():
    root = Path(__file__).parents[2]
    capture = (root / "scripts/capture_ostium_crypto_economics.sh").read_text()
    installer = (root / "scripts/install_ostium_crypto_capture_cron.sh").read_text()
    assert 'OSTIUM_CRYPTO_PAIRS:-"BTC/USD ETH/USD"' in capture
    assert 'capture_ostium_economics_set.sh' in capture
    assert "capture_binance_book_ticker_v4" in capture
    assert "crypto_proxy_mapping_v4 observe" in capture
    assert "crypto_proxy_mapping_v4 gate" in capture
    assert "ostium_native_coverage_gate" in capture
    assert "crypto_h4_market_preflight_v4" in capture
    assert "CRYPTO_H4_PREFLIGHT_REFRESH_FAILED" in capture
    assert 'LINE="17 * * * * flock -n $LOCK ' in installer
    assert "tradingagent-ostium-crypto-economics.lock" in installer


def test_universe_cron_samples_hourly_without_overlap():
    script = (Path(__file__).parents[2] / "scripts" /
              "install_ostium_research_universe_capture_cron.sh").read_text()
    assert 'LINE="37 * * * 1-5 flock -n $LOCK ' in script
    assert "tradingagent-ostium-research-universe-economics.lock" in script
