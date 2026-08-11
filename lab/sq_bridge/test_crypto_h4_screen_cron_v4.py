from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_screen_worker_is_separate_bounded_and_sqcli_free():
    runner = (ROOT / "scripts/run_crypto_h4_screen_workers.sh").read_text()
    installer = (ROOT / "scripts/install_crypto_h4_screen_cron.sh").read_text()
    assert "crypto_h4_screen_worker_v4" in runner
    assert "btcusd ethusd" in runner
    assert "ALQUIMIA_CRYPTO_SCREEN_MAX_CHUNKS:-1" in runner
    assert "ALQUIMIA_CRYPTO_SCREEN_CHUNK_SIZE:-25" in runner
    assert "sqcli" not in runner.lower()
    assert "3,13,23,33,43,53 * * * * flock -n" in installer
    assert "tradingagent-crypto-h4-screen-v4.lock" in installer
    assert "/mnt/volume-SQ/user/alquimia_runtime/crypto_h4_screen_v4" in installer
