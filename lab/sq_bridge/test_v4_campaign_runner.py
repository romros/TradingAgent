import json
import sys
from pathlib import Path

from lab.sq_bridge.v4_campaign_runner import run_next, status


ROOT = Path(__file__).parent
METHODOLOGY = ROOT / "methodology_v4.json"


def make_helper(tmp_path: Path) -> Path:
    helper = tmp_path / "stage_helper.py"
    helper.write_text("""
import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])
from lab.sq_bridge.e2e_control import payload

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
        candidate_path.write_bytes(f'runner-test:{candidate}'.encode())
        paths[candidate] = candidate_path.name
        hashes[candidate] = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    artifact['candidate_artifact_paths'] = paths
    artifact['candidate_artifact_hashes'] = hashes
if stage == 'python_translation':
    base = Path(os.environ['ALQUIMIA_STAGE_ARTIFACT']).parent
    sqx_path = base / 'runner-sqx-001.sqx'
    ir_path = base / 'runner-sqx-001.ir.json'
    ir_path.write_text('{"runner_test":true}')
    artifact['sqx_path'] = sqx_path.name
    artifact['sqx_sha256'] = hashlib.sha256(sqx_path.read_bytes()).hexdigest()
    artifact['canonical_ir_path'] = ir_path.name
    artifact['canonical_ir_sha256'] = hashlib.sha256(ir_path.read_bytes()).hexdigest()
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
