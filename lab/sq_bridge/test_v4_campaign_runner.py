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

stage = os.environ['ALQUIMIA_STAGE']
decision = sys.argv[1] if len(sys.argv) > 1 else 'PASS'
stages = json.loads(Path(sys.argv[2]).read_text())['stages']
ids = ['runner-sqx-001'] if stages.index(stage) >= stages.index('sq_generation') else []
holdout = stage in {'python_translation', 'parity', 'paper'}
artifact = payload(stage, ids, holdout)
artifact['campaign_id'] = 'runner-test'
artifact['evidence_class'] = 'observed'
artifact.pop('control_purpose', None)
artifact['decision'] = decision
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
    manifest_path.write_text(json.dumps({
        'schema_version': 1, 'methodology_id': 'alquimia-v4-coverage-before-performance',
        'project_name': 'RUNNER_PROJECT',
        'generation_type': 'genetic-evolution', 'attempt_budget': 1,
        'output_sha256': 'b' * 64, 'canonical_evaluation_capital': 200,
        'holdout_sealed': True, 'source_role': 'xml_format_scaffold_only'}))
    artifact['sq_project_manifest_path'] = manifest_path.name
    artifact['sq_project_manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
if stage == 'python_translation':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    sqx_path = base / 'runner-sqx-001.sqx'
    ir_path = base / 'runner-sqx-001.ir.json'
    translate(sqx_path, ir_path)
    artifact['sqx_path'] = sqx_path.name
    artifact['sqx_sha256'] = hashlib.sha256(sqx_path.read_bytes()).hexdigest()
    artifact['canonical_ir_path'] = ir_path.name
    artifact['canonical_ir_sha256'] = hashlib.sha256(ir_path.read_bytes()).hexdigest()
if stage == 'parity':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    report_path = base / 'runner-sqx-001.parity.json'
    report_path.write_text(json.dumps({
        'schema_version': 1, 'candidate_id': 'runner-sqx-001',
        'signal_match_rate': 1.0, 'trade_match_rate': 1.0,
        'candle_coverage_pct': 95, 'pnl_correlation': .99}))
    artifact['parity_report_path'] = report_path.name
    artifact['parity_report_sha256'] = hashlib.sha256(report_path.read_bytes()).hexdigest()
if stage == 'paper':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    config_path = base / 'runner-sqx-001.paper.json'
    config_path.write_text(json.dumps({
        'schema_version': 1, 'candidate_id': 'runner-sqx-001', 'capital_usdc': 200,
        'mode': 'paper', 'live_authorized': False, 'signer_enabled': False}))
    artifact['paper_config_path'] = config_path.name
    artifact['paper_config_sha256'] = hashlib.sha256(config_path.read_bytes()).hexdigest()
if decision == 'BAD':
    artifact['decision'] = 'PASS'
    artifact.pop('historical_period_coverage', None)
if decision != 'PASS':
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
        "hypothesis_id": "runner-hypothesis", "market": "XAUUSD",
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


def test_runner_can_checkpoint_all_nine_native_stages(tmp_path):
    manifest = make_manifest(tmp_path)
    results = [run_next(manifest) for _ in range(9)]
    assert all(result["status"] == "STAGE_RECORDED" for result in results)
    final = status(manifest)
    assert final["status"] == "COMPLETE"
    assert final["paper_ready"] is True
    assert final["live_authorized"] is False
    assert len(json.loads((tmp_path / "state/chain.json").read_text())["receipts"]) == 9


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
