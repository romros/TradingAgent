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


def test_universe_capture_prioritizes_eurusd_and_is_failure_isolated():
    script = (Path(__file__).parents[2] / "scripts" /
              "capture_ostium_research_universe_economics.sh").read_text()
    assert 'PAIRS=${OSTIUM_RESEARCH_PAIRS:-"EUR/USD ' in script
    assert 'CAPTURE_FAILED pair=%s' in script
    assert 'PREFLIGHT_REFRESH_FAILED pair=EUR/USD' in script
    assert 'exit "$STATUS"' in script
