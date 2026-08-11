import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_screen_worker_v4 import run


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "lab/sq_bridge/evidence/crypto_h4_experiment_design_v4.json"
SEMANTICS = ROOT / "lab/sq_bridge/crypto_h4_signal_semantics_v4.json"


def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def _write(path, value): path.write_text(json.dumps(value)); return path


def test_blocked_preflight_never_touches_other_inputs_or_state(tmp_path):
    preflight = _write(tmp_path / "preflight.json", {
        "decision": "BLOCK", "campaign_id": "btcusd-h4-alquimia-v4",
        "blocking_reasons": ["MAPPING"]})
    output = tmp_path / "state"
    result = run(preflight_path=preflight, design_path=tmp_path / "absent-design",
                 semantics_path=tmp_path / "absent-semantics", output_dir=output)
    assert result["decision"] == "WAITING_FOR_MARKET_PREFLIGHT"
    assert result["market_data_accessed"] is False
    assert result["performance_accessed"] is False
    assert not output.exists()


def _ready(tmp_path):
    source = tmp_path / "source.csv"
    rows = []
    for index in range(40):
        day, slot = divmod(index, 6)
        rows.append(f"2018.03.{day + 1:02d},{slot * 4:02d}:00,100,101,99,100,1")
    source.write_text("\n".join(rows) + "\n")
    canonical = _write(tmp_path / "canonical.json", {
        "research_symbol": "BTCUSD", "canonical_path": str(source),
        "canonical_sha256": _sha(source)})
    zero = {f"{scenario}_annual_cost_pct": 0 for scenario in
            ("base", "conservative", "stress")}
    costs = _write(tmp_path / "costs.json", {
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "by_notional": {"200": {f"{scenario}_roundtrip_bps": 10 for scenario in
                                  ("base", "conservative", "stress")}},
        "carry": {"long": zero, "short": zero},
        "paper_authorized": False, "live_authorized": False})
    preflight = _write(tmp_path / "preflight.json", {
        "stage": "market_preflight", "decision": "PASS",
        "research_authorized": True, "next_stage_authorized": "hypothesis_screen",
        "campaign_id": "btcusd-h4-alquimia-v4", "market": "BTCUSD",
        "account_usdc": 200, "timeframe": "H4", "input_receipts": {
            "canonical_source": {"path": str(canonical), "sha256": _sha(canonical)},
            "costs": {"path": str(costs), "sha256": _sha(costs)}}})
    return preflight


def test_ready_worker_writes_atomic_chunks_and_resumes(tmp_path):
    preflight, output = _ready(tmp_path), tmp_path / "state"
    first = run(preflight_path=preflight, design_path=DESIGN,
                semantics_path=SEMANTICS, output_dir=output,
                max_chunks=1, chunk_size=2)
    assert first["decision"] == "SCREEN_RUNNING"
    chunks = list(output.glob("*/chunk_*.json"))
    assert len(chunks) == 1
    assert json.loads(chunks[0].read_text())["end_attempt"] == 2
    second = run(preflight_path=preflight, design_path=DESIGN,
                 semantics_path=SEMANTICS, output_dir=output,
                 max_chunks=1, chunk_size=2)
    chunks = sorted(output.glob("*/chunk_*.json"))
    assert len(chunks) == 2
    assert json.loads(chunks[-1].read_text())["start_attempt"] == 3
    assert second["holdout_accessed"] is False
    assert second["sqcli_started"] is False


def test_resume_rejects_tampered_chunk(tmp_path):
    preflight, output = _ready(tmp_path), tmp_path / "state"
    run(preflight_path=preflight, design_path=DESIGN,
        semantics_path=SEMANTICS, output_dir=output, max_chunks=1, chunk_size=1)
    chunk = next(output.glob("*/chunk_*.json"))
    value = json.loads(chunk.read_text())
    value["rows"][0]["parameters"]["shift"] = 99
    chunk.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="replay design"):
        run(preflight_path=preflight, design_path=DESIGN,
            semantics_path=SEMANTICS, output_dir=output,
            max_chunks=1, chunk_size=1)
