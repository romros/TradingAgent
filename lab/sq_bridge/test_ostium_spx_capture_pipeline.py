from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_collector_runs_raw_summary_cost_and_preflight_in_order():
    script = (ROOT / "scripts/capture_ostium_spx_session_quotes.sh").read_text()
    collector = script.index("collect_ostium_execution_quotes.mjs")
    summary = script.index("summarize_execution_quotes.py")
    costs = script.index("spxusd_small_account_cost_gate.py")
    preflight = script.index("us500_d1_market_preflight_v4.py")
    trigger = script.index("lab.sq_bridge.us500_v4_screen_trigger")
    assert collector < summary < costs < preflight < trigger
    assert 'market_preflight_latest.json' in script
    assert 'us500_d1_market_preflight_v4_config.json' in script
    assert 'us500_d1_canonical_v4.csv' in script
