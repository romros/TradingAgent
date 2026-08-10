import json
import sys
from pathlib import Path

from lab.sq_bridge.v4_campaign_runner import run_next, status


ROOT = Path(__file__).parent
METHODOLOGY = ROOT / "methodology_v4.json"


def make_helper(tmp_path: Path) -> Path:
    helper = tmp_path / "stage_helper.py"
    helper.write_text("""
import hashlib, json, os, sys, zipfile
from pathlib import Path
sys.path.insert(0, sys.argv[3])
from lab.sq_bridge.e2e_control import payload
from lab.sq_bridge.test_sqx_extract import STRATEGY, SETTINGS
from lab.sq_bridge.sqx_to_ir import translate
from lab.sq_bridge.parity_artifact_v4 import build_artifact as build_parity
from lab.sq_bridge.final_holdout_artifact_v4 import build_artifact as build_holdout
from lab.sq_bridge.paper_package_artifact_v4 import build_artifact as build_paper
from lab.sq_bridge.temporal_validation_artifact_v4 import build_artifact as build_temporal
from lab.sq_bridge.robustness_artifact_v4 import build_artifact as build_robustness
from lab.sq_bridge.small_account_artifact_v4 import build_artifact as build_small_account
from lab.sq_bridge.hypothesis_screen_artifact_v4 import build_artifact as build_screen
from lab.sq_bridge.temporal_split_contract_v4 import build_contract as build_split, digest as split_digest
from lab.sq_bridge.us500_d1_market_preflight_v4 import compose as compose_preflight

stage = os.environ['ALQUIMIA_STAGE']
decision = sys.argv[1] if len(sys.argv) > 1 else 'PASS'
stages = json.loads(Path(sys.argv[2]).read_text())['stages']
ids = ['runner-sqx-001'] if stages.index(stage) >= stages.index('sq_generation') else []
holdout = stage == 'final_holdout_validation'
artifact = payload(stage, ids, holdout)
artifact['campaign_id'] = 'runner-test'
artifact['evidence_class'] = 'observed'
artifact.pop('control_purpose', None)
artifact['decision'] = decision
if stage == 'market_preflight':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    (base / 'coverage.json').write_text(json.dumps({
        'decision': 'PASS_HISTORICAL_COVERAGE', 'performance_accessed': False,
        'historical_coverage_pass': True, 'historical_expected_observations': 100,
        'historical_complete_observations': 95, 'historical_overall_coverage_ratio': .95,
        'historical_minimum_period_coverage_ratio': .85,
        'historical_period_coverage': {'train-a': .85, 'train-b': .95}}))
    (base / 'mapping.json').write_text(json.dumps({
        'decision': 'PASS_D1_SOURCE_MAPPING', 'performance_accessed': False,
        'common_complete_session_coverage_ratio': .99,
        'd1_close_return_correlation': .999}))
    (base / 'costs.json').write_text(json.dumps({
        'decision': 'PASS_COSTS_FROZEN', 'costs_frozen': True,
        'by_notional': {'200': {'base_roundtrip_bps': 0,
                                'conservative_roundtrip_bps': 1,
                                'stress_roundtrip_bps': 2}},
        'carry': {side: {scenario + '_annual_cost_pct': 0
                         for scenario in ('base', 'conservative', 'stress')}
                  for side in ('long', 'short')},
        'paper_authorized': False, 'live_authorized': False}))
    config_path = base / 'preflight-config.json'
    config_path.write_text(json.dumps({
        'schema_version': 1, 'campaign_id': 'runner-test',
        'ostium_pair_id': 'control-pair', 'coverage': 'coverage.json',
        'mapping': 'mapping.json', 'costs': 'costs.json'}))
    artifact = compose_preflight(config_path)
if stage == 'hypothesis_screen':
    from datetime import date, timedelta
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    cost_path = base / 'costs.json'
    cost_hash = hashlib.sha256(cost_path.read_bytes()).hexdigest()
    trace_path = base / 'hypothesis-screen.trace.json'
    source_path = base / 'canonical-control.csv'
    source_rows, source_day = [], date(2000, 1, 3)
    while len(source_rows) < 500:
        if source_day.weekday() < 5:
            source_rows.append(f'{source_day:%Y.%m.%d},00:00,1,1.1,.9,1,1')
        source_day += timedelta(days=1)
    source_path.write_text('\\n'.join(source_rows) + '\\n')
    split = json.loads(Path(sys.argv[2]).read_text())['temporal_split']
    split_contract = build_split(source_path, Path(sys.argv[2]))
    train_rows = len(source_rows) * split['train_pct'] // 100
    variants = []
    for variant_id in ('central', 'neighbor-a', 'neighbor-b'):
        variants.append({
            'variant_id': variant_id,
            'neighbor_of': None if variant_id == 'central' else 'central',
            'trades': [{'trade_id': f'{variant_id}-trade-{index:02d}',
                        'entry_timestamp': (date(2000, 1, 3)
                            + timedelta(days=index * 2)).isoformat() + 'T00:00:00+00:00',
                        'exit_timestamp': (date(2000, 1, 4)
                            + timedelta(days=index * 2)).isoformat() + 'T00:00:00+00:00',
                        'gross_return_pct': .5 if index < 30 else -.25,
                        'side': 'long' if index % 2 == 0 else 'short',
                        'holding_days': 1}
                       for index in range(50)]})
    trace_path.write_text(json.dumps({
        'schema_version': 1, 'trace_type': 'hypothesis_screen_grid_trace',
        'train_only': True, 'future_periods_accessed': False,
        'holdout_accessed': False, 'cost_model_sha256': cost_hash,
        'screen_notional_usdc': 200,
        'source_path': str(source_path.resolve()),
        'source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
        'source_rows': len(source_rows), 'train_rows': train_rows,
        'source_first_utc': '2000-01-03T00:00:00+00:00',
        'train_end_utc': source_rows[train_rows - 1].split(',', 1)[0].replace('.', '-')
            + 'T00:00:00+00:00',
        'temporal_split': split,
        'temporal_contract': split_contract,
        'temporal_contract_sha256': split_digest(split_contract),
        'hypotheses': [{'hypothesis_id': 'hypothesis-control',
                        'central_variant_id': 'central', 'variants': variants}]}))
    artifact = build_screen(
        campaign_id='runner-test', trace_path=trace_path,
        cost_model_path=cost_path,
        methodology_path=Path(sys.argv[2]),
        artifact_path=Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']))
if stage == 'sq_generation':
    paths, hashes = {}, {}
    for candidate in ids:
        candidate_path = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent / f'{candidate}.sqx'
        settings = SETTINGS.replace(b'>T</StrategyName>',
                                    f'>{candidate}</StrategyName>'.encode())
        with zipfile.ZipFile(candidate_path, 'w') as archive:
            archive.writestr('strategy_Portfolio.xml', STRATEGY)
            archive.writestr('settings.xml', settings)
            archive.writestr('version.txt', '3')
        paths[candidate] = candidate_path.name
        hashes[candidate] = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    artifact['candidate_artifact_paths'] = paths
    artifact['candidate_artifact_hashes'] = hashes
    artifact['rules_per_candidate'] = {candidate: 1 for candidate in ids}
    artifact['entry_condition_counts_per_candidate'] = {
        candidate: {'long': 1, 'short': 1} for candidate in ids}
    inventory = [{'path': paths[candidate], 'sha256': hashes[candidate]} for candidate in ids]
    inventory_digest = hashlib.sha256(''.join(
        f\"{row['path']}:{row['sha256']}\\n\" for row in inventory).encode()).hexdigest()
    watchdog_path = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent / 'watchdog-status.json'
    watchdog_path.write_text(json.dumps({
        'project': 'RUNNER_PROJECT', 'generated': 1, 'state': 'BUDGET_REACHED',
        'reason': 'ATTEMPT_BUDGET', 'artifacts': inventory}))
    artifact['sq_watchdog_status_path'] = watchdog_path.name
    artifact['sq_watchdog_status_sha256'] = hashlib.sha256(watchdog_path.read_bytes()).hexdigest()
    artifact['databank_path'] = '.'
    artifact['databank_candidate_count'] = len(inventory)
    artifact['databank_inventory_sha256'] = inventory_digest
    manifest_path = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent / 'runner-project.manifest.json'
    chain_path = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent.parent / 'chain.json'
    chain = json.loads(chain_path.read_text())
    prerequisite_chain_path = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent / 'runner-project.prerequisites.json'
    prerequisite_chain_path.write_text(json.dumps(chain, indent=2, sort_keys=True) + '\\n')
    manifest_path.write_text(json.dumps({
        'schema_version': 1, 'methodology_id': 'alquimia-v4-coverage-before-performance',
        'project_name': 'RUNNER_PROJECT',
        'generation_type': 'genetic-evolution', 'attempt_budget': 1,
        'output_sha256': 'b' * 64, 'canonical_evaluation_capital': 200,
        'holdout_sealed': True, 'source_role': 'xml_format_scaffold_only',
        'campaign_id': 'runner-test', 'source_hypothesis_id': 'hypothesis-control',
        'evidence_chain_path': str(prerequisite_chain_path),
        'evidence_chain_sha256': hashlib.sha256(prerequisite_chain_path.read_bytes()).hexdigest(),
        'market_preflight_receipt_sha256': chain['receipts'][0]['receipt_sha256'],
        'hypothesis_screen_receipt_sha256': chain['receipts'][1]['receipt_sha256']}))
    artifact['sq_project_manifest_path'] = manifest_path.name
    artifact['sq_project_manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    artifact['prerequisite_evidence_chain_path'] = str(prerequisite_chain_path)
    artifact['prerequisite_evidence_chain_sha256'] = hashlib.sha256(
        prerequisite_chain_path.read_bytes()).hexdigest()
if stage == 'temporal_validation':
    from datetime import datetime, timedelta, timezone
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    cost_path = base / 'costs.json'
    cost_hash = hashlib.sha256(cost_path.read_bytes()).hexdigest()
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    train = [{'trade_id': f'train-{index:02d}',
              'exit_timestamp': (start + timedelta(days=index + 1)).isoformat(),
              'gross_return_pct': .5 if index < 18 else -.25,
              'side': 'long' if index % 2 == 0 else 'short', 'holding_days': 1}
             for index in range(30)]
    windows = []
    for window_index in range(3):
        window_start = start + timedelta(days=40 + window_index * 20)
        windows.append({
            'window_id': f'w{window_index + 1}',
            'start_utc': window_start.isoformat(),
            'end_utc': (window_start + timedelta(days=11)).isoformat(),
            'trades': [{'trade_id': f'oos-{window_index}-{index:02d}',
                        'exit_timestamp': (window_start + timedelta(days=index + 1)).isoformat(),
                        'gross_return_pct': .5 if index < 6 else -.25,
                        'side': 'long' if index % 2 == 0 else 'short',
                        'holding_days': 1}
                       for index in range(10)]})
    trace_path = base / 'runner-sqx-001.temporal.trace.json'
    trace_path.write_text(json.dumps({
        'schema_version': 1, 'trace_type': 'temporal_validation_trade_trace',
        'candidate_id': 'runner-sqx-001', 'capital_usdc': 200,
        'holdout_accessed': False, 'cost_scenario': 'base',
        'cost_model_sha256': cost_hash, 'evaluation_notional_usdc': 200,
        'train_end_utc': (start + timedelta(days=31)).isoformat(),
        'train_trades': train, 'oos_windows': windows}))
    artifact = build_temporal(
        campaign_id='runner-test', trace_paths=[trace_path],
        cost_model_path=cost_path,
        methodology_path=Path(sys.argv[2]),
        artifact_path=Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']))
if stage == 'robustness':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    cost_path = base / 'costs.json'
    cost_hash = hashlib.sha256(cost_path.read_bytes()).hexdigest()
    trace_path = base / 'runner-sqx-001.robustness.trace.json'
    trace_path.write_text(json.dumps({
        'schema_version': 1, 'trace_type': 'robustness_simulation_trace',
        'candidate_id': 'runner-sqx-001', 'capital_usdc': 200,
        'holdout_accessed': False, 'tested_leverage': 5,
        'venue_max_leverage': 100,
        'liquidation_model': 'ostium_threshold_cost_buffered', 'cost_stress_multiplier': 2,
        'cost_model_sha256': cost_hash, 'evaluation_notional_usdc': 200,
        'monte_carlo_runs': [
            {'run_id': f'run-{index:04d}',
             'gross_pnl_usdc': 3.0 if index < 700 else -1.0,
             'trade_count': 30, 'long_holding_days': 15,
             'short_holding_days': 15,
             'maximum_adverse_excursion_pct': 2.0,
             'maximum_adverse_excursion_side': 'long' if index % 2 == 0 else 'short',
             'maximum_adverse_excursion_holding_days': 1.0}
            for index in range(1000)],
        'parameter_variants': [
            {'variant_id': f'variant-{index}',
             'perturbation_pct': -10 if index % 2 == 0 else 10,
             'gross_pnl_usdc': 3.0 if index < 3 else -1.0,
             'trade_count': 30, 'long_holding_days': 15,
             'short_holding_days': 15}
            for index in range(4)],
        'stress_trades': [
            {'gross_return_pct': .5 if index < 18 else -.25,
             'side': 'long' if index % 2 == 0 else 'short', 'holding_days': 1}
            for index in range(30)]}))
    artifact = build_robustness(
        campaign_id='runner-test', trace_paths=[trace_path],
        cost_model_path=cost_path,
        methodology_path=Path(sys.argv[2]),
        artifact_path=Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']))
if stage == 'small_account_economics':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    cost_path = base / 'frozen-costs.json'
    carry = {scenario + '_annual_cost_pct': 0
             for scenario in ('base', 'conservative', 'stress')}
    cost_path.write_text(json.dumps({
        'decision': 'PASS_COSTS_FROZEN', 'costs_frozen': True,
        'by_notional': {'500': {'base_roundtrip_bps': 0,
                                'conservative_roundtrip_bps': 1,
                                'stress_roundtrip_bps': 2}},
        'carry': {'long': carry, 'short': carry}}))
    cost_hash = hashlib.sha256(cost_path.read_bytes()).hexdigest()
    trace_path = base / 'runner-sqx-001.small-account.trace.json'
    trace_path.write_text(json.dumps({
        'schema_version': 1, 'trace_type': 'small_account_trade_trace',
        'candidate_id': 'runner-sqx-001', 'capital_usdc': 200,
        'holdout_accessed': False, 'stop_loss_required': True,
        'risk_per_trade_pct': 1.5, 'stop_distance_pct': 1,
        'venue_max_leverage': 100, 'cost_model_sha256': cost_hash,
        'trades': [
            {'trade_id': f'trade-{index:02d}',
             'gross_return_pct': .5 if index < 18 else -.2,
             'side': 'long' if index % 2 == 0 else 'short',
             'holding_days': 1}
            for index in range(30)]}))
    artifact = build_small_account(
        campaign_id='runner-test', trace_paths=[trace_path],
        robustness_artifact_path=base / '05_robustness.json',
        cost_model_path=cost_path,
        methodology_path=Path(sys.argv[2]),
        artifact_path=Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']))
if stage == 'python_translation':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    sqx_path = base / 'runner-sqx-001.sqx'
    ir_path = base / 'runner-sqx-001.ir.json'
    translate(sqx_path, ir_path)
    artifact['sqx_path'] = sqx_path.name
    artifact['sqx_sha256'] = hashlib.sha256(sqx_path.read_bytes()).hexdigest()
    artifact['canonical_ir_path'] = ir_path.name
    artifact['canonical_ir_sha256'] = hashlib.sha256(ir_path.read_bytes()).hexdigest()
if stage == 'final_holdout_validation':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    sizing_path = base / '06_small_account_economics.json'
    sizing = json.loads(sizing_path.read_text())
    cost_path = base / 'frozen-costs.json'
    cost_hash = hashlib.sha256(cost_path.read_bytes()).hexdigest()
    sizing_hash = hashlib.sha256(sizing_path.read_bytes()).hexdigest()
    trace_path = base / 'runner-sqx-001.holdout.trace.json'
    trades = []
    for index in range(20):
        win = index < 12
        trades.append({'trade_id': f't{index:02d}',
                       'gross_return_pct': .5 if win else -.15,
                       'side': 'long' if index % 2 == 0 else 'short',
                       'holding_days': 1})
    trace_path.write_text(json.dumps({
        'schema_version': 1, 'trace_type': 'final_holdout_trade_trace',
        'candidate_id': 'runner-sqx-001', 'capital_usdc': 200,
        'selection_frozen_before_holdout': True,
        'parameters_changed_after_holdout': False,
        'holdout_evaluation_count': 1,
        'position_notional_usdc': sizing['position_notional_usdc'],
        'selected_leverage': sizing['selected_leverage'],
        'cost_model_sha256': cost_hash,
        'small_account_artifact_sha256': sizing_hash,
        'trades': trades}))
    artifact = build_holdout(
        campaign_id='runner-test', candidate_id='runner-sqx-001', trace_path=trace_path,
        small_account_artifact_path=sizing_path, cost_model_path=cost_path,
        methodology_path=Path(sys.argv[2]),
        artifact_path=Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']))
if stage == 'parity':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    from datetime import datetime, timedelta, timezone
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candles = [(start + timedelta(days=index)).isoformat() for index in range(60)]
    common = {
        'schema_version': 1, 'trace_type': 'strategy_parity_trace',
        'candidate_id': 'runner-sqx-001', 'candles': candles,
        'signals': [{'timestamp': candles[index],
                     'direction': 'long' if index % 2 == 0 else 'short'}
                    for index in range(30)],
        'trades': [{'entry_timestamp': candles[index], 'exit_timestamp': candles[index + 1],
                    'direction': 'long' if index % 2 == 0 else 'short',
                    'pnl': float(index % 5 - 2)} for index in range(30)]}
    sq_trace = base / 'runner-sqx-001.sq.trace.json'
    python_trace = base / 'runner-sqx-001.python.trace.json'
    sq_trace.write_text(json.dumps({**common, 'source': 'strategyquant'}))
    python_trace.write_text(json.dumps({**common, 'source': 'python'}))
    report_path = base / 'runner-sqx-001.parity.json'
    artifact = build_parity(
        campaign_id='runner-test', candidate_id='runner-sqx-001',
        sq_trace_path=sq_trace, python_trace_path=python_trace,
        methodology_path=Path(sys.argv[2]), report_path=report_path,
        artifact_path=Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']))
if stage == 'paper':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    config_path = base / 'runner-sqx-001.paper.json'
    artifact = build_paper(
        campaign_id='runner-test', candidate_id='runner-sqx-001',
        source_artifact_paths={
            'market_preflight': base / '01_market_preflight.json',
            'small_account_economics': base / '06_small_account_economics.json',
            'final_holdout_validation': base / '07_final_holdout_validation.json',
            'python_translation': base / '08_python_translation.json',
            'parity': base / '09_parity.json'},
        config_path=config_path,
        artifact_path=Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']))
if decision == 'BAD':
    artifact['decision'] = 'PASS'
    artifact.pop('historical_period_coverage', None)
if decision in {'REJECT', 'BLOCK'}:
    artifact['decision'] = decision
    artifact['candidate_ids'] = []
Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).write_text(json.dumps(artifact))
print('license code: RUNNER-SECRET-123')
print('runner diagnostic ' * 2000, file=sys.stderr)
""")
    return helper


def make_manifest(tmp_path: Path, *, reject_stage: str | None = None,
                  fail_stage: str | None = None, bad_stage: str | None = None) -> Path:
    helper = make_helper(tmp_path)
    methodology = json.loads(METHODOLOGY.read_text())
    stages = {}
    for stage in methodology["stages"]:
        if stage == fail_stage:
            command = ["/bin/false"]
        else:
            decision = ("BAD" if stage == bad_stage else
                        ("REJECT" if stage == reject_stage else "PASS"))
            command = [sys.executable, str(helper), decision, str(METHODOLOGY),
                       str(ROOT.parents[1])]
        stages[stage] = {"command": command, "timeout_seconds": 10, "cwd": str(ROOT.parents[1])}
    manifest = tmp_path / "campaign.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "campaign_id": "runner-test",
        "hypothesis_id": "hypothesis-control", "market": "XAUUSD",
        "methodology": str(METHODOLOGY), "state_dir": str(tmp_path / "state"),
        "stages": stages,
    }))
    return manifest


def test_runner_records_one_valid_stage_at_a_time_and_reaches_sq_only_after_screen(tmp_path):
    manifest = make_manifest(tmp_path)
    assert status(manifest)["status"] == "NOT_STARTED"
    first = run_next(manifest)
    assert first["stage"] == "market_preflight"
    assert first["next_stage"] == "hypothesis_screen"
    chain = json.loads((tmp_path / "state/chain.json").read_text())
    assert [row["stage"] for row in chain["receipts"]] == ["market_preflight"]
    second = run_next(manifest)
    assert second["stage"] == "hypothesis_screen"
    assert second["next_stage"] == "sq_generation"
    assert not (tmp_path / "state/artifacts/03_sq_generation.json").exists()
    third = run_next(manifest)
    assert third["stage"] == "sq_generation"
    assert third["next_stage"] == "temporal_validation"


def test_terminal_rejection_prevents_sq_command(tmp_path):
    manifest = make_manifest(tmp_path, reject_stage="hypothesis_screen")
    assert run_next(manifest)["decision"] == "PASS"
    rejected = run_next(manifest)
    assert rejected["decision"] == "REJECT"
    assert rejected["terminal"] is True
    assert run_next(manifest)["status"] == "NO_WORK"
    assert not (tmp_path / "state/artifacts/03_sq_generation.json").exists()


def test_failed_stage_keeps_chain_unchanged_and_is_retryable(tmp_path):
    manifest = make_manifest(tmp_path, fail_stage="market_preflight")
    failed = run_next(manifest)
    assert failed["status"] == "STAGE_COMMAND_FAILED"
    assert failed["chain_unchanged"] is True
    chain = json.loads((tmp_path / "state/chain.json").read_text())
    assert chain["receipts"] == []


def test_runner_can_checkpoint_all_ten_native_stages(tmp_path):
    manifest = make_manifest(tmp_path)
    results = [run_next(manifest) for _ in range(10)]
    assert all(result["status"] == "STAGE_RECORDED" for result in results)
    final = status(manifest)
    assert final["status"] == "COMPLETE"
    assert final["paper_ready"] is True
    assert final["live_authorized"] is False
    assert len(json.loads((tmp_path / "state/chain.json").read_text())["receipts"]) == 10


def test_manifest_change_requires_a_new_campaign_state(tmp_path):
    manifest = make_manifest(tmp_path)
    assert run_next(manifest)["status"] == "STAGE_RECORDED"
    changed = json.loads(manifest.read_text())
    changed["stages"]["hypothesis_screen"]["timeout_seconds"] = 11
    manifest.write_text(json.dumps(changed))
    result = run_next(manifest)
    assert result["status"] == "MANIFEST_CHANGED"
    assert result["chain_unchanged"] is True
    assert len(json.loads((tmp_path / "state/chain.json").read_text())["receipts"]) == 1


def test_invalid_artifact_is_removed_without_advancing_chain(tmp_path):
    manifest = make_manifest(tmp_path, bad_stage="market_preflight")
    result = run_next(manifest)
    assert result["status"] == "STAGE_ARTIFACT_REJECTED"
    assert result["chain_unchanged"] is True
    assert json.loads((tmp_path / "state/chain.json").read_text())["receipts"] == []
    assert not (tmp_path / "state/artifacts/01_market_preflight.json").exists()


def test_logs_are_bounded_hashed_and_redact_secrets(tmp_path):
    manifest = make_manifest(tmp_path)
    assert run_next(manifest)["status"] == "STAGE_RECORDED"
    log_path = tmp_path / "state/logs/01_market_preflight.json"
    raw_log = log_path.read_text()
    log = json.loads(raw_log)
    assert "RUNNER-SECRET-123" not in raw_log
    assert log["stdout_summary"]["redacted_tail"] == "license code: ***\n"
    assert len(log["stdout_summary"]["sha256"]) == 64
    assert log["stderr_summary"]["truncated"] is True
    assert len(log["stderr_summary"]["redacted_tail"].encode()) <= 16 * 1024
