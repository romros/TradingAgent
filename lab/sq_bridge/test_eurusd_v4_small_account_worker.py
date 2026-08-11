import hashlib
import json

from lab.sq_bridge.candle_source_contract_v4 import build as build_candles
from lab.sq_bridge.eurusd_v4_small_account_worker import tick


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return path


def _fixture(tmp_path):
    campaign = "eurusd-d1-alquimia-v4"
    robustness_dir, output = tmp_path / "robustness", tmp_path / "small"
    methodology = _write(tmp_path / "methodology.json", {})
    costs = _write(tmp_path / "costs.json", {
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True})
    robust = _write(robustness_dir / "05_robustness.json", {
        "stage": "robustness", "decision": "PASS", "campaign_id": campaign,
        "holdout_accessed": False, "candidate_ids": ["A"],
        "candidate_robustness_metrics": {"A": {}},
        "cost_model_path": str(costs), "cost_model_sha256": _sha(costs),
        "methodology_path": str(methodology), "methodology_sha256": _sha(methodology)})
    _write(robustness_dir / "robustness_worker_receipt.json", {
        "decision": "PASS_ROBUSTNESS", "campaign_id": campaign,
        "candidate_ids": ["A"], "robustness_artifact_path": str(robust),
        "robustness_artifact_sha256": _sha(robust)})
    sq = tmp_path / "sq.csv"
    sq.write_text("Date,Time,Open,High,Low,Close,Volume\n2020.01.01,00:00,1,2,0.5,1.5,1\n")
    duka = tmp_path / "duka.csv"; duka.write_bytes(sq.read_bytes())
    contract = _write(tmp_path / "candle.json", build_candles(
        sq_candles_path=sq, sq_timezone="UTC",
        dukascopy_candles_path=duka, dukascopy_timezone="UTC",
        symbol="EURUSD", timeframe="D1"))
    config = _write(tmp_path / "config.json", {
        "small_account_candle_contract_path": str(contract),
        "small_account_candle_contract_sha256": _sha(contract),
        "market": {"symbol": "EURUSD", "timeframe": "D1",
                   "source_timezone": "Etc/UTC", "ostium_pair_id": "2",
                   "ostium_pair_from": "EUR", "ostium_pair_to": "USD",
                   "ostium_category": "forex"}})
    return robustness_dir, output, config


def test_waits_for_robustness_and_terminal_reject_never_sizes(tmp_path):
    result = tick(
        robustness_worker_dir=tmp_path / "absent", output_dir=tmp_path / "out",
        worker_config_path=tmp_path / "missing")
    assert result["decision"] == "WAITING_FOR_ROBUSTNESS"
    robustness, output, config = _fixture(tmp_path)
    receipt = robustness / "robustness_worker_receipt.json"
    value = json.loads(receipt.read_text())
    value.update({"decision": "REJECT_ROBUSTNESS", "candidate_ids": []})
    receipt.write_text(json.dumps(value))
    called = []
    result = tick(
        robustness_worker_dir=robustness, output_dir=output,
        worker_config_path=config,
        small_account_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "REJECT_ROBUSTNESS"
    assert called == []


def test_sizes_200_usdc_from_frozen_sources_and_replays_receipt(tmp_path):
    robustness, output, config = _fixture(tmp_path)
    calls = []

    def small(**kwargs):
        calls.append(kwargs)
        value = {"stage": "small_account_economics", "decision": "PASS",
                 "candidate_ids": ["A"], "selected_leverage": 10,
                 "evaluated_candidate_small_account_metrics": {"A": {}},
                 "holdout_accessed": False}
        _write(kwargs["artifact_path"], value)
        return value

    common = dict(robustness_worker_dir=robustness, output_dir=output,
                  worker_config_path=config, small_account_fn=small)
    first = tick(**common)
    assert first["decision"] == "PASS_SMALL_ACCOUNT"
    assert first["capital_usdc"] == 200
    assert first["selected_leverage"] == 10
    assert calls[0]["candle_timezone"] == "UTC"
    assert tick(**common) == first
    assert len(calls) == 1


def test_rejects_tampered_candle_source_before_sizing(tmp_path):
    robustness, output, config = _fixture(tmp_path)
    contract = json.loads(config.read_text())["small_account_candle_contract_path"]
    value = json.loads(open(contract).read())
    with open(value["sq_candles_path"], "a") as handle:
        handle.write("tampered\n")
    called = []
    try:
        tick(robustness_worker_dir=robustness, output_dir=output,
             worker_config_path=config,
             small_account_fn=lambda **kwargs: called.append(kwargs))
    except ValueError as error:
        assert "manipulada" in str(error)
    else:
        raise AssertionError("tampered candles were accepted")
    assert called == []
